"use client";

/**
 * The support child's assignments — given here, checked here (founder
 * 2026-08-04).
 *
 * **This is per-student homework, not a new thing.** `homework_assignments`
 * has carried a nullable `student_id` since V2-P3, `homework_results` records
 * the exception rows, and `core/homework_verdict.py` owns what `late`,
 * `carried` and `not_checked` are worth. A support-specific assignment table
 * would be a second definition of *did the child do the work* — the defect this
 * codebase has now closed six times — and it would also mean the child's own
 * homework history quietly disagreed with his support page.
 *
 * So the whole block is a mounting of machinery that already exists:
 * `addHomework` with `student_id` set, `checkHomework` with a roster of one,
 * and `StudentHomeworkHistory` for the record.
 *
 * The verdicts are the module's five, not a checkbox. **`not_checked` is the
 * teacher's gap and never renders as the child's miss** (HW-1's load-bearing
 * rule) — which is why "not checked yet" is a state here and not an absence of
 * one, and why giving an assignment and never opening it can never read as the
 * child having failed to do it.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { NotebookPen, Plus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { HomeworkStatus, StudentHomeworkItem } from "@/lib/school-types";

/** The five verdicts, in the module's own words. `done` and `late` both count
 * as done; `carried` and `waived` leave the denominator; `not_checked` is the
 * teacher's gap. Never invent a sixth here — import the vocabulary. */
const VERDICTS: { key: HomeworkStatus; label: string }[] = [
  { key: "done", label: "Done" },
  { key: "late", label: "Late" },
  { key: "partial", label: "Partly" },
  { key: "not_done", label: "Not done" },
  { key: "carried", label: "Was absent" },
];

const TONE: Partial<Record<HomeworkStatus, "success" | "neutral" | "warning">> = {
  done: "success",
  late: "success",
  partial: "warning",
  not_done: "warning",
  carried: "neutral",
  waived: "neutral",
};

function Item({
  item, studentId, onChecked,
}: {
  item: StudentHomeworkItem;
  studentId: string;
  onChecked: () => void;
}) {
  const check = useMutation({
    // A roster of one, through the endpoint the class check sheet uses — so the
    // verdict lands in the same rows with the same arithmetic. Capture by
    // exception holds even here: "done" is the empty exception set, which is
    // also what stamps the assignment as CHECKED rather than leaving it in
    // `not_checked`.
    mutationFn: (status: HomeworkStatus) =>
      schoolApi.checkHomework(item.assignment_id, {
        results: status === "done" ? [] : [{ student_id: studentId, status }],
      }),
    onSuccess: () => {
      toast.success("Recorded");
      onChecked();
    },
    onError: (e) => showApiError(e, "Could not record it"),
  });

  return (
    <li className="flex flex-wrap items-center gap-2 border-t border-border py-2.5 first:border-t-0">
      <div className="min-w-0 flex-1">
        <p className="text-sm">{item.text}</p>
        <p className="text-xs text-muted-foreground">
          {item.date}
          {item.due_date ? ` · due ${item.due_date}` : ""}
          {item.personal ? " · just for him" : ""}
        </p>
      </div>
      {item.status === "not_checked" ? (
        // Never "not done": nobody has looked at it yet.
        <span className="text-xs text-muted-foreground">not checked yet</span>
      ) : (
        <Badge tone={TONE[item.status] ?? "neutral"}>{item.status.replace("_", " ")}</Badge>
      )}
      <select
        className="rounded-md border border-border bg-card px-2 py-1 text-xs"
        value=""
        disabled={check.isPending}
        onChange={(e) => {
          if (e.target.value) check.mutate(e.target.value as HomeworkStatus);
        }}
      >
        <option value="">mark…</option>
        {VERDICTS.map((v) => (
          <option key={v.key} value={v.key}>
            {v.label}
          </option>
        ))}
      </select>
    </li>
  );
}

export function SupportAssignments({
  studentId, classSubjectId,
}: {
  studentId: string;
  /** Null when the child's class isn't taught this subject — then there is
   *  nothing to file an assignment against, and we say so rather than
   *  offering a button that 404s. */
  classSubjectId: string | null;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [due, setDue] = useState("");

  const { data } = useQuery({
    queryKey: ["homework-student", studentId, 30],
    queryFn: () => schoolApi.studentHomework(studentId, 30),
  });

  const give = useMutation({
    mutationFn: () =>
      schoolApi.addHomework({
        class_subject_id: classSubjectId!,
        text: text.trim(),
        due_date: due || null,
        student_id: studentId,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["homework-student", studentId] });
      toast.success("Given — his guardians are told, and it shows on his page");
      setText("");
      setDue("");
      setOpen(false);
    },
    onError: (e) => showApiError(e, "Could not give the assignment"),
  });

  const items = data?.items ?? [];

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">
          <NotebookPen className="h-4 w-4" /> Assignments
        </h2>
        {classSubjectId ? (
          <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4" /> Give an assignment
          </Button>
        ) : null}
      </div>

      {items.length ? (
        <ul className="mt-2">
          {items.map((i) => (
            <Item
              key={i.assignment_id}
              item={i}
              studentId={studentId}
              onChecked={() =>
                qc.invalidateQueries({ queryKey: ["homework-student", studentId] })
              }
            />
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">
          Nothing set in the last 30 days.
        </p>
      )}

      {data && data.not_checked ? (
        // The teacher's gap, said as the teacher's gap.
        <p className="mt-2 text-xs text-muted-foreground">
          {data.not_checked} of these {data.not_checked === 1 ? "has" : "have"} not been
          checked by anyone yet — that is not the same as not done.
        </p>
      ) : null}

      <Sheet open={open} onOpenChange={setOpen} title="Give an assignment">
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            Just for this child. It appears in his homework like any other, and his
            guardians are notified — so he gets the work and you get the record.
          </p>
          <div>
            <Label htmlFor="hw">What to do</Label>
            <input
              id="hw"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="read page 24 aloud to a parent, twice"
              className="mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
            />
          </div>
          <div>
            <Label htmlFor="due">Due (optional)</Label>
            <input
              id="due"
              type="date"
              value={due}
              onChange={(e) => setDue(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
            />
          </div>
          <Button
            className="w-full"
            disabled={!text.trim() || give.isPending}
            onClick={() => give.mutate()}
          >
            Give it
          </Button>
        </div>
      </Sheet>
    </section>
  );
}
