"use client";

/**
 * Students → Academics → Class logs (founder, 2026-08-05).
 *
 * The register of what each class was actually taught, and the door to add to
 * it from a desk rather than from a period card between rooms.
 *
 * **Two kinds of entry, and keeping them apart is the whole screen.**
 *
 *   Whole class   a `lesson_logs` row. It is what the syllabus board counts,
 *                 what the forecast paces against, and what a parent's coverage
 *                 percentage divides by.
 *   Named children a `lesson_observations` line about those children only. It
 *                 counts towards NOTHING — a lesson that reached three children
 *                 is not coverage, and filing it as coverage would inflate
 *                 every pace figure in the school.
 *
 * The form makes that a visible choice ("Whole class" / "Only some children")
 * rather than a checkbox with consequences nobody can see, and the register
 * marks each row so the distinction survives being read back.
 *
 * Picking a syllabus topic is offered but never required: a school that does
 * not track topic by topic, or a period that was not on the plan, types what
 * happened. Only a picked topic moves the syllabus — free text is a record of
 * the day, which is the honest thing for it to be.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Plus, Trash2, Users, X } from "lucide-react";
import { useCallback, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ClassSubjectPicker } from "@/components/students/class-subject-picker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import { todayKey } from "@/lib/format";
import type { ClassLogEntry } from "@/lib/school-types";
import { cn } from "@/lib/utils";

function AddEntry({ classSubjectId, classId, onDone }: {
  classSubjectId: string; classId: string; onDone: () => void;
}) {
  const [scope, setScope] = useState<"class" | "students">("class");
  const [date, setDate] = useState(todayKey());
  const [topicId, setTopicId] = useState("");
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const [coverage, setCoverage] = useState<"full" | "partial">("full");
  const [picked, setPicked] = useState<string[]>([]);

  const { data: units = [] } = useQuery({
    queryKey: ["syllabus", classSubjectId],
    queryFn: () => schoolApi.syllabus(classSubjectId),
  });
  const { data: roster = [] } = useQuery({
    queryKey: ["students", "class", classId],
    queryFn: () => schoolApi.students({ class_id: classId }),
    enabled: scope === "students",
  });

  const add = useMutation({
    mutationFn: () => schoolApi.addClassLog({
      class_subject_id: classSubjectId,
      date,
      topic_id: topicId || null,
      title: title.trim() || null,
      coverage,
      note: note.trim() || null,
      student_ids: scope === "students" ? picked : [],
    }),
    onSuccess: () => {
      toast.success(scope === "class"
        ? "Logged for the class"
        : `Logged for ${picked.length} student${picked.length === 1 ? "" : "s"}`);
      setTopicId(""); setTitle(""); setNote(""); setPicked([]);
      onDone();
    },
    onError: (e) => showApiError(e, "Could not save the entry"),
  });

  const ready = (!!topicId || !!title.trim())
    && (scope === "class" || picked.length > 0);

  return (
    <form
      className="space-y-3 rounded-xl border border-border bg-card p-4 shadow-sm"
      onSubmit={(e) => { e.preventDefault(); if (ready) add.mutate(); }}
    >
      <div className="flex flex-wrap items-center gap-2">
        {/* A visible choice, not a side effect. Only the left one moves the
            syllabus, and the caption under it says so. */}
        {([["class", "Whole class", Users], ["students", "Only some children", BookOpen]] as const)
          .map(([key, label, Icon]) => (
            <button key={key} type="button" onClick={() => setScope(key)}
              className={cn(
                "flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm font-medium",
                scope === key
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border text-muted-foreground hover:bg-muted")}>
              <Icon className="h-3.5 w-3.5" />{label}
            </button>
          ))}
        <Input type="date" className="ml-auto w-40" value={date}
          onChange={(e) => setDate(e.target.value)} />
      </div>
      <p className="text-xs text-muted-foreground">
        {scope === "class"
          ? "Counts towards the syllabus for this class."
          : "A line about these children only — it does not move the syllabus."}
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <Label>Chapter · topic</Label>
          <select
            className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
            value={topicId}
            onChange={(e) => setTopicId(e.target.value)}
          >
            <option value="">— none, I&apos;ll write it —</option>
            {units.map((u) => (
              <optgroup key={u.id} label={u.title}>
                {u.topics.map((t) => (
                  <option key={t.id} value={t.id}>{t.title}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </div>
        <div>
          <Label>{topicId ? "Note (optional)" : "What happened"}</Label>
          {topicId ? (
            <Input value={note} onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. covered the first half only" />
          ) : (
            <Input value={title} onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Revision before the chapter test" />
          )}
        </div>
      </div>

      {scope === "class" && topicId ? (
        <div className="flex items-center gap-2 text-sm">
          <Label className="mb-0">Coverage</Label>
          {(["full", "partial"] as const).map((c) => (
            <button key={c} type="button" onClick={() => setCoverage(c)}
              className={cn("rounded-full border px-2.5 py-1 text-xs font-medium",
                coverage === c ? "border-primary bg-primary text-primary-foreground"
                  : "border-border text-muted-foreground hover:bg-muted")}>
              {c === "full" ? "finished it" : "part of it"}
            </button>
          ))}
        </div>
      ) : null}

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
          {topicId ? null : null}
          <div className="mt-2">
            <Label>Note (optional)</Label>
            <Input value={note} onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. re-explained condensation at his desk" />
          </div>
        </div>
      ) : null}

      <Button type="submit" disabled={!ready || add.isPending}>
        {add.isPending ? "Saving…" : "Add entry"}
      </Button>
    </form>
  );
}

function EntryRow({ e, canWrite, onDelete }: {
  e: ClassLogEntry; canWrite: boolean; onDelete: (id: string) => void;
}) {
  const heading = e.topic_title ?? e.title ?? "—";
  return (
    <tr className="border-b border-border/60 bg-card last:border-0">
      <td className="whitespace-nowrap px-3 py-2.5 align-top text-xs text-muted-foreground tabular-nums">
        {e.date}
        {e.period_no ? <span className="block">period {e.period_no}</span> : null}
      </td>
      <td className="px-3 py-2.5 align-top">
        <span className="flex flex-wrap items-center gap-1.5">
          <span className="font-medium">{heading}</span>
          {e.kind === "student" ? (
            // Marked so the distinction survives being read back: this row is
            // about one child and counted towards nothing.
            <Badge tone="neutral" className="text-[10px]">
              {e.student_name}
            </Badge>
          ) : e.coverage === "partial" ? (
            <Badge tone="warning" className="text-[10px]">part of it</Badge>
          ) : null}
        </span>
        {e.unit_title ? (
          <span className="block text-[11px] text-muted-foreground">{e.unit_title}</span>
        ) : null}
        {e.note ? <p className="mt-0.5 text-xs text-muted-foreground">{e.note}</p> : null}
      </td>
      <td className="px-3 py-2.5 align-top text-xs text-muted-foreground">
        {e.teacher_name ?? "—"}
      </td>
      <td className="px-3 py-2.5 text-right align-top">
        {canWrite ? (
          <button type="button" aria-label="Remove entry"
            onClick={() => onDelete(e.id)}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-danger">
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        ) : null}
      </td>
    </tr>
  );
}

function ClassLogs() {
  const qc = useQueryClient();
  const [sel, setSel] = useState<{ classId: string | null; subjectCsId: string | null }>(
    { classId: null, subjectCsId: null });
  const [adding, setAdding] = useState(false);
  const onChange = useCallback(
    (next: { classId: string | null; subjectCsId: string | null }) => setSel(next), []);

  const { data: book } = useQuery({
    queryKey: ["class-log", sel.subjectCsId],
    queryFn: () => schoolApi.classLogBook({ classSubjectId: sel.subjectCsId! }),
    enabled: !!sel.subjectCsId,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["class-log", sel.subjectCsId] });
  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteClassLog(id),
    onSuccess: () => { refresh(); toast.success("Entry removed"); },
    onError: (e) => showApiError(e, "Could not remove the entry"),
  });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Class logs</h1>
          <p className="text-sm text-muted-foreground">
            What each class was taught — and lines about individual children.
          </p>
        </div>
        {book?.can_write ? (
          <Button size="sm" variant={adding ? "ghost" : "primary"}
            onClick={() => setAdding(!adding)}>
            {adding ? <><X className="h-4 w-4" /> Close</> : <><Plus className="h-4 w-4" /> Add entry</>}
          </Button>
        ) : null}
      </div>

      <ClassSubjectPicker classId={sel.classId} subjectCsId={sel.subjectCsId}
        onChange={onChange} />

      {adding && sel.subjectCsId && sel.classId ? (
        <div className="mb-4">
          <AddEntry classSubjectId={sel.subjectCsId} classId={sel.classId}
            onDone={() => { refresh(); setAdding(false); }} />
        </div>
      ) : null}

      {!book ? null : book.entries.length === 0 ? (
        <EmptyState icon={BookOpen} title="Nothing logged yet"
          body={book.can_write
            ? "Add the first entry above, or log it from the period card as you teach."
            : "Nothing has been recorded for this subject in the last 90 days."} />
      ) : (
        <div className="overflow-hidden rounded-xl border border-border shadow-sm">
          <div className="flex items-center gap-2 border-b border-border bg-card px-3 py-2">
            <p className="text-sm font-semibold">
              {book.class_label} · {book.subject_name}
            </p>
            <span className="text-xs text-muted-foreground">
              {book.entries.length} entr{book.entries.length === 1 ? "y" : "ies"} since {book.since}
            </span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[620px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                  <th className="px-3 py-2 font-medium">When</th>
                  <th className="px-3 py-2 font-medium">What</th>
                  <th className="px-3 py-2 font-medium">By</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {book.entries.map((e) => (
                  <EntryRow key={e.id} e={e} canWrite={book.can_write}
                    onDelete={(id) => remove.mutate(id)} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ClassLogsPage() {
  return (
    <AuthGuard>
      <ClassLogs />
    </AuthGuard>
  );
}
