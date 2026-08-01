"use client";

// The homework check sheet (V1-5 — `D-85`, `D-34`, `S-85`, `S-89`, `S-97`).
//
// Capture-by-exception, exactly like attendance: **"Everyone did it ✓" is one
// tap** and writes an empty exception set. The roster only opens when somebody
// didn't. Typing a count told us how many and never *who*, so nobody could be
// followed up and no parent could be told whether their own child had done it.
//
// Three things this sheet puts in front of her at the one moment she is holding
// the notebooks — the cheapest intervention point in the product:
//
//   `S-85`  **was absent when it was set** — shown, and deliberately **not**
//           preselected. A friend may have passed the work on, and a hard
//           exclusion is one she could not override. Absent is not a refusal.
//   `S-97`  **items still carried** from while they were away, so she is not
//           asked to remember what she is already holding.
//   `S-89`  **the miss streak** — until V1-5 this number lived only on the
//           principal's dashboard, which is the wrong end of the school.
//
// And the rule that outranks the lot, inherited from HW-1: **a homework with no
// check row is `not_checked`, which is never "everyone did it"** and never a
// child's miss. That is why "Everyone did it" must be an explicit tap and can
// never be the default state of the screen.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCheck } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { HomeworkVerdict } from "@/lib/school-types";
import { cn } from "@/lib/utils";

/** The tap cycle. `done` is the absence of a row, so it is the start and the end.
 *
 *  Order is the frequency a teacher actually needs: the two verdicts about the
 *  work first, then `late` (a status she may set whenever she likes — no
 *  threshold, nothing expires, `D-85`), then the two that are about the child
 *  being away rather than about the work (`D-34`, `S-98`). */
const CYCLE: (HomeworkVerdict | null)[] =
  [null, "not_done", "partial", "late", "carried", "waived"];

const VERDICT: Record<HomeworkVerdict, { label: string; tone: "success" | "warning" | "danger" | "neutral"; cls: string }> = {
  done: { label: "did it", tone: "success", cls: "border-border bg-card" },
  not_done: { label: "didn’t", tone: "danger", cls: "border-danger/40 bg-danger/8" },
  partial: { label: "partly", tone: "warning", cls: "border-warning/50 bg-warning-soft" },
  // `late` counts as DONE in every completion figure and is reported beside it,
  // never inside it (`S-99`). So it is not a warning colour.
  late: { label: "late", tone: "success", cls: "border-success/40 bg-success/8" },
  // Absent when it was set. Neutral on purpose — this is not a miss (`D-34`),
  // and colouring it would put a child off sick at the top of a red list.
  carried: { label: "was away", tone: "neutral", cls: "border-dashed border-border bg-muted/40" },
  waived: { label: "let go", tone: "neutral", cls: "border-dashed border-border bg-muted/40" },
};

export function HomeworkCheckSheet({
  assignmentId, onDone, compact = false,
}: {
  assignmentId: string;
  onDone?: () => void;
  compact?: boolean;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [marks, setMarks] = useState<Record<string, HomeworkVerdict>>({});
  const [seededFor, setSeededFor] = useState<string | null>(null);

  const { data: sheet } = useQuery({
    queryKey: ["homework-sheet", assignmentId],
    queryFn: () => schoolApi.homeworkSheet(assignmentId),
    enabled: open,
  });

  // Seed the working copy from whatever was recorded last time (derived, no
  // effect). Reopening the sheet shows what she said, so a mis-tap is fixable —
  // the server does a full replace, exactly like attendance.
  if (sheet && seededFor !== assignmentId) {
    setMarks(Object.fromEntries(
      sheet.roster.filter((r) => r.status !== "done").map((r) => [r.student_id, r.status]),
    ) as Record<string, HomeworkVerdict>);
    setSeededFor(assignmentId);
  }

  const settle = () => {
    qc.invalidateQueries({ queryKey: ["homework-queue"] });
    qc.invalidateQueries({ queryKey: ["my-day"] });
    qc.invalidateQueries({ queryKey: ["homework-sheet", assignmentId] });
    setOpen(false);
    onDone?.();
  };

  const check = useMutation({
    mutationFn: (results: { student_id: string; status: string }[]) =>
      schoolApi.checkHomework(assignmentId, { results }),
    onSuccess: (res) => {
      const missed = res.not_done_count + res.partial_count;
      toast.success(missed === 0 ? "Recorded — everyone did it" : `Recorded — ${missed} didn’t`);
      settle();
    },
    onError: (e) => showApiError(e, "Could not record"),
  });

  const cycle = (studentId: string) => {
    const now = marks[studentId] ?? null;
    const next = CYCLE[(CYCLE.indexOf(now) + 1) % CYCLE.length];
    const copy = { ...marks };
    if (next === null) delete copy[studentId];
    else copy[studentId] = next;
    setMarks(copy);
  };

  if (!open) {
    return (
      <div className="flex flex-wrap gap-2">
        {/* One tap for the norm. It is an explicit press, never a default —
            silence means `not_checked`, which is the teacher's gap. */}
        <Button size="sm" disabled={check.isPending} onClick={() => check.mutate([])}>
          <CheckCheck className="h-4 w-4" /> Everyone did it
        </Button>
        <Button size="sm" variant="outline" onClick={() => setOpen(true)}>Some didn’t…</Button>
      </div>
    );
  }
  if (!sheet) return <div className="h-24 animate-pulse rounded-md bg-muted" />;

  const graded = sheet.roster.filter((r) => {
    const v = marks[r.student_id];
    return v !== "carried" && v !== "waived";
  }).length;
  const missed = Object.values(marks).filter((v) => v === "not_done" || v === "partial").length;

  return (
    <>
      <p className="mb-1.5 text-xs text-muted-foreground">
        Tap a name to cycle: didn’t → partly → late → was away → let go → did it.
      </p>
      <div className={cn("mb-2 grid gap-1", compact ? "" : "sm:grid-cols-2")}>
        {sheet.roster.map((r) => {
          const v = marks[r.student_id];
          const style = VERDICT[v ?? "done"];
          return (
            <button key={r.student_id} type="button" onClick={() => cycle(r.student_id)}
              className={cn(
                "flex items-center gap-2 rounded-md border px-2.5 py-2 text-left text-sm active:scale-[0.99]",
                style.cls)}>
              <span className="min-w-0 flex-1 truncate">
                {r.roll_no ? `${r.roll_no}. ` : ""}{r.full_name}
              </span>
              {/* S-85 — a fact she may act on, never a preselection. */}
              {r.absent_when_set && !v ? (
                <span className="shrink-0 rounded border border-dashed border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  was absent
                </span>
              ) : null}
              {/* S-97 — she is already holding these. */}
              {r.carried_pending > 0 ? (
                <span className="shrink-0 rounded border border-dashed border-border px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  {r.carried_pending} carried
                </span>
              ) : null}
              {/* S-89 — the intervention, at the moment it is cheapest. */}
              {r.miss_streak >= 2 ? (
                <Badge tone="warning">{r.miss_streak} in a row</Badge>
              ) : null}
              {v ? <Badge tone={style.tone}>{style.label}</Badge> : null}
            </button>
          );
        })}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button size="sm" disabled={check.isPending}
          onClick={() => check.mutate(
            Object.entries(marks).map(([student_id, status]) => ({ student_id, status })))}>
          Save — {graded - missed} of {graded} did it
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
        {/* The denominator says so out loud: carried and waived are OUT of it. */}
        {sheet.roster.length !== graded ? (
          <span className="text-xs text-muted-foreground">
            {sheet.roster.length - graded} not counted (away or let go)
          </span>
        ) : null}
      </div>
    </>
  );
}
