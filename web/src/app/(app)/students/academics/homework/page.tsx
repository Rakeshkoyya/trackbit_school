"use client";

/**
 * Students → Academics → Homework (founder, 2026-08-05).
 *
 * What was set for a class-subject, and how it came back. Same shape as Class
 * logs next door — pick a class, pick a subject, read the register, add to it —
 * because they are the same act at two different times of day.
 *
 * **The rule this screen exists to keep visible:** a `homework_checks` row means
 * the teacher went through it, and its ABSENCE means `not_checked`, which is
 * never "everybody did it" and never a child's miss (HW-1). So an unchecked row
 * renders the dashed no-record texture and the words "not checked yet" — it has
 * no completion figure at all, because a 0% there would blame forty children
 * for a teacher who has not opened the books.
 *
 * Setting homework for **named children** writes one assignment row EACH, never
 * a shared row with a list on it: every reader in the product keys on
 * (assignment, student), so a shared row would have to teach all of them a
 * second shape and a child's history would stop being one row per piece of work.
 *
 * Checking stays where it belongs — `/homework` is the desk (`D-36`), and each
 * row links into it rather than growing a second check sheet here.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ClipboardCheck, Plus, X } from "lucide-react";
import Link from "next/link";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { PaceBar } from "@/components/charts";
import { ClassSubjectPicker } from "@/components/students/class-subject-picker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { HomeworkLogEntry } from "@/lib/school-types";
import { cn } from "@/lib/utils";

function SetHomework({ classSubjectId, classId, onDone }: {
  classSubjectId: string; classId: string; onDone: () => void;
}) {
  const [scope, setScope] = useState<"class" | "students">("class");
  const [text, setText] = useState("");
  const [due, setDue] = useState("");
  const [picked, setPicked] = useState<string[]>([]);

  const { data: roster = [] } = useQuery({
    queryKey: ["students", "class", classId],
    queryFn: () => schoolApi.students({ class_id: classId }),
    enabled: scope === "students",
  });

  const add = useMutation({
    mutationFn: () => schoolApi.addHomework({
      class_subject_id: classSubjectId,
      text: text.trim(),
      due_date: due || null,
      student_ids: scope === "students" ? picked : [],
    }),
    onSuccess: (res) => {
      // P3: the teacher's payback for logging it — the guardians already know.
      toast.success(`Homework set · ${res.notified_count} parents notified`);
      setText(""); setDue(""); setPicked([]);
      onDone();
    },
    onError: (e) => showApiError(e, "Could not set homework"),
  });

  const ready = text.trim().length > 0 && (scope === "class" || picked.length > 0);

  return (
    <form className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm"
      onSubmit={(e) => { e.preventDefault(); if (ready) add.mutate(); }}>
      <div className="flex flex-wrap items-center gap-2">
        {([["class", "Whole class"], ["students", "Only some children"]] as const)
          .map(([key, label]) => (
            <button key={key} type="button" onClick={() => setScope(key)}
              className={cn("rounded-full border px-3 py-1.5 text-sm font-medium",
                scope === key ? "border-primary bg-primary text-primary-foreground"
                  : "border-border text-muted-foreground hover:bg-muted")}>
              {label}
            </button>
          ))}
        <span className="ml-auto flex items-center gap-2">
          <Label className="mb-0 text-xs">Due</Label>
          <Input type="date" className="w-40" value={due}
            onChange={(e) => setDue(e.target.value)} />
        </span>
      </div>

      <div>
        <Label>Homework</Label>
        <Input autoFocus value={text} onChange={(e) => setText(e.target.value)}
          placeholder="e.g. Exercise 4, questions 1–8" />
      </div>

      {scope === "students" ? (
        <div>
          <Label>Which children</Label>
          <div className="flex flex-wrap gap-1.5">
            {roster.map((s) => {
              const on = picked.includes(s.id);
              return (
                <button key={s.id} type="button"
                  onClick={() => setPicked(on
                    ? picked.filter((x) => x !== s.id) : [...picked, s.id])}
                  className={cn("rounded-full border px-2.5 py-1 text-xs",
                    on ? "border-primary bg-primary text-primary-foreground"
                      : "border-border text-muted-foreground hover:bg-muted")}>
                  {s.full_name}
                </button>
              );
            })}
          </div>
          <p className="mt-1.5 text-xs text-muted-foreground">
            Only these children&apos;s guardians are told.
          </p>
        </div>
      ) : null}

      <Button type="submit" disabled={!ready || add.isPending}>
        {add.isPending ? "Setting…" : "Set homework"}
      </Button>
    </form>
  );
}

/** How it came back, or the honest absence of an answer. */
function OutcomeCell({ e }: { e: HomeworkLogEntry }) {
  if (!e.checked) {
    return (
      <span className="flex w-36 flex-col gap-1">
        <PaceBar pct={null} />
        <span className="text-[11px] italic text-muted-foreground">not checked yet</span>
      </span>
    );
  }
  // `completion` is a 0–1 fraction (`core/coverage.completion_pct`), multiplied
  // at the render site exactly as every other homework surface does it — the
  // arithmetic lives in one place and the scaling is the caller's.
  const pct = e.completion == null ? null : Math.round(e.completion * 100);
  const tone = pct == null ? "neutral" : pct >= 90 ? "green" : pct >= 70 ? "amber" : "red";
  return (
    <span className="flex w-36 flex-col gap-1">
      <PaceBar pct={pct} tone={tone} />
      <span className="text-[11px] text-muted-foreground tabular-nums">
        {pct == null ? "—" : `${pct}% of ${e.roster}`}
        {e.late ? ` · ${e.late} late` : ""}
      </span>
      {e.carried || e.waived ? (
        // Neither is a miss (`D-34`/`S-98`) — they leave the denominator, and
        // saying so is what stops a child off sick reading as a refusal.
        <span className="text-[11px] text-muted-foreground">
          {e.carried ? `${e.carried} was absent` : ""}
          {e.carried && e.waived ? " · " : ""}
          {e.waived ? `${e.waived} waived` : ""}
        </span>
      ) : null}
    </span>
  );
}

function HomeworkLog() {
  const qc = useQueryClient();
  const [sel, setSel] = useState<{ classId: string | null; subjectCsId: string | null }>(
    { classId: null, subjectCsId: null });
  const [adding, setAdding] = useState(false);
  const onChange = useCallback(
    (next: { classId: string | null; subjectCsId: string | null }) => setSel(next), []);

  const { data: book } = useQuery({
    queryKey: ["homework-book", sel.subjectCsId],
    queryFn: () => schoolApi.homeworkBook({ classSubjectId: sel.subjectCsId! }),
    enabled: !!sel.subjectCsId,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["homework-book", sel.subjectCsId] });

  const unchecked = (book?.entries ?? []).filter((e) => !e.checked).length;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Homework</h1>
          <p className="text-sm text-muted-foreground">
            What was set, and how it came back.
          </p>
        </div>
        {book?.can_write ? (
          <Button size="sm" variant={adding ? "ghost" : "primary"}
            onClick={() => setAdding(!adding)}>
            {adding ? <><X className="h-4 w-4" /> Close</> : <><Plus className="h-4 w-4" /> Set homework</>}
          </Button>
        ) : null}
      </div>

      <ClassSubjectPicker classId={sel.classId} subjectCsId={sel.subjectCsId}
        onChange={onChange} />

      {adding && sel.subjectCsId && sel.classId ? (
        <div className="mb-4">
          <SetHomework classSubjectId={sel.subjectCsId} classId={sel.classId}
            onDone={() => { refresh(); setAdding(false); }} />
        </div>
      ) : null}

      {unchecked > 0 ? (
        <p className="mb-3 text-sm text-muted-foreground">
          {unchecked} set{unchecked === 1 ? "" : "s"} nobody has gone through yet —{" "}
          <Link href="/homework" className="text-primary hover:underline">
            check them at the desk
          </Link>.
        </p>
      ) : null}

      {!book ? null : book.entries.length === 0 ? (
        <EmptyState icon={ClipboardCheck} title="No homework recorded"
          body={book.can_write
            ? "Set the first one above — the guardians are told the moment you do."
            : "Nothing has been set for this subject in the last 90 days."} />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border shadow-sm">
          <div className="flex items-center gap-2 border-b border-border bg-card px-3 py-2">
            <p className="text-sm font-semibold">
              {book.class_label} · {book.subject_name}
            </p>
            <span className="text-xs text-muted-foreground">
              {book.entries.length} since {book.since}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[680px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Set</th>
                  <th className="px-3 py-2 font-medium">What</th>
                  <th className="px-3 py-2 font-medium">How it came back</th>
                  <th className="px-3 py-2 font-medium">Checked by</th>
                </tr>
              </thead>
              <tbody>
                {book.entries.map((e) => (
                  <tr key={e.id} className="border-b border-border/60 bg-card last:border-0">
                    <td className="whitespace-nowrap px-3 py-2.5 align-top text-xs text-muted-foreground tabular-nums">
                      {e.date}
                      {e.due_date ? (
                        <span className="block">due {e.due_date}</span>
                      ) : null}
                    </td>
                    <td className="px-3 py-2.5 align-top">
                      <Link href={`/homework?assignment=${e.id}`}
                        className="font-medium hover:underline">{e.text}</Link>
                      {e.student_name ? (
                        <Badge tone="neutral" className="ml-1.5 text-[10px]">
                          {e.student_name}
                        </Badge>
                      ) : null}
                    </td>
                    <td className="px-3 py-2.5 align-top"><OutcomeCell e={e} /></td>
                    <td className="px-3 py-2.5 align-top text-xs text-muted-foreground">
                      {e.checked_by ?? (e.checked ? "—" : "")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AcademicsHomeworkPage() {
  return (
    <AuthGuard>
      <HomeworkLog />
    </AuthGuard>
  );
}
