"use client";

/**
 * Plan → Exams (founder, 2026-08-05) — the school's own exam calendar.
 *
 * A school holds two kinds of exam and the product only had a screen for one.
 * A slip test is a thing a teacher does on a Tuesday. **The exam** is declared
 * in April, sat by every class, and issues a report card — and that is what a
 * parent means by "exams". It had no surface at all: `calendar_events` with
 * `type='exam_block'` has been the exam calendar since V2-P7 (the planner paces
 * against it, the portion maps chapters onto it), but the only way to create one
 * was to paint a date on the year grid.
 *
 * So this screen is two levels:
 *
 *   1. **the exams**, with dates — the admin adds, edits and removes them; a
 *      teacher reads exactly the same list with the pencils absent. Not a
 *      different screen for her: a locked list is a fact about permission, and
 *      showing her a second, thinner one would hide what the school has
 *      declared.
 *   2. **the papers**, class × subject, once an exam is picked. A cell either
 *      holds a recorded paper or is an empty slot, and the cell she may OPEN
 *      TO EDIT is decided by the server (`can_edit`) — her own subject.
 *
 * The asymmetry in level 2 is the design, not an oversight: a teacher may read
 * every subject of every class she is assigned to (she has to, to talk to a
 * family about a child) and may write only her own. Rendering a colleague's row
 * read-only is a courtesy; the refusal lives in `ExamService.save`.
 *
 * Nothing here writes a mark. Capture is `ExamCapture` — the same component the
 * scores page uses, with the subject pinned and the block's id attached — so
 * there is one write path for every mark in the product and no second place for
 * "did he sit it" to be answered.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarDays, ChevronRight, Lock, Pencil, Plus, Trash2,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { ExamCapture } from "@/components/school/exam-capture";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Modal } from "@/components/ui/modal";
import { PageLoading } from "@/components/ui/page-loading";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type {
  MainExamBody, MainExamDetail, MainExamRow, MainExamSubjectRow,
} from "@/lib/school-types";
import { cn } from "@/lib/utils";

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN",
    { day: "2-digit", month: "short" });

const STATE: Record<string, { label: string; tone: "success" | "warning" | "neutral" }> = {
  running: { label: "on now", tone: "warning" },
  upcoming: { label: "upcoming", tone: "neutral" },
  past: { label: "sat", tone: "success" },
};

// ── the admin's add/edit sheet ───────────────────────────────────────────────
function ExamSheet({ open, onOpenChange, yearId, exam, onSaved }: {
  open: boolean; onOpenChange: (v: boolean) => void;
  yearId: string | null; exam: MainExamRow | null; onSaved: () => void;
}) {
  const [title, setTitle] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [notes, setNotes] = useState("");
  const [affects, setAffects] = useState(true);
  const [seeded, setSeeded] = useState<string | null>(null);

  // Seed once per exam opened — an effect here would fight the user's typing.
  const key = exam?.exam_event_id ?? "new";
  if (open && seeded !== key) {
    setSeeded(key);
    setTitle(exam?.title ?? "");
    setStart(exam?.start_date ?? "");
    setEnd(exam?.end_date ?? exam?.start_date ?? "");
    setNotes(exam?.notes ?? "");
    setAffects(exam?.affects_teaching ?? true);
  }
  if (!open && seeded !== null) setSeeded(null);

  const save = useMutation({
    mutationFn: () => {
      const body: MainExamBody = {
        title: title.trim(), start_date: start, end_date: end || start,
        notes: notes.trim() || null, affects_teaching: affects,
        ...(exam ? {} : { academic_year_id: yearId }),
      };
      return exam
        ? schoolApi.updateMainExam(exam.exam_event_id, body)
        : schoolApi.createMainExam(body);
    },
    onSuccess: () => {
      toast.success(exam ? "Exam updated" : "Exam added");
      onSaved();
      onOpenChange(false);
    },
    onError: (e) => showApiError(e, "Could not save the exam"),
  });

  const ready = title.trim() && start;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}
      title={exam ? "Edit exam" : "Add an exam"}>
      <div className="space-y-4">
        <p className="text-[12px] leading-snug text-muted-foreground">
          The dates the whole school sits this exam. Every class&apos;s papers
          hang off it, and the planner paces the syllabus against it.
        </p>
        <div>
          <Label>Name</Label>
          <Input placeholder="Half-yearly examination" value={title}
            onChange={(e) => setTitle(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Starts</Label>
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          </div>
          <div>
            <Label>Ends</Label>
            <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          </div>
        </div>
        <div>
          <Label>Note (optional)</Label>
          <Input placeholder="Classes 6–10 only" value={notes}
            onChange={(e) => setNotes(e.target.value)} />
        </div>
        <label className="flex items-start gap-2.5 rounded-lg border border-border p-3">
          <input type="checkbox" checked={affects} className="mt-0.5"
            onChange={(e) => setAffects(e.target.checked)} />
          <span className="text-[13px] leading-snug">
            Teaching stops on these days
            <span className="mt-0.5 block text-[11px] text-muted-foreground">
              Leave this on for a normal exam week — the planner removes those
              days from every subject&apos;s capacity, which is what makes
              &ldquo;this chapter lands after the exam&rdquo; true. Turn it off
              for a test held inside its own period.
            </span>
          </span>
        </label>
        <Button className="w-full" disabled={!ready || save.isPending}
          onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : exam ? "Save changes" : "Add exam"}
        </Button>
      </div>
    </Sheet>
  );
}

// ── level 2: one exam's papers ───────────────────────────────────────────────
function PaperCell({ row, classId, exam, onSaved }: {
  row: MainExamSubjectRow; classId: string; exam: MainExamDetail;
  onSaved: () => void;
}) {
  const [open, setOpen] = useState(false);
  const recorded = row.cycle_id != null;

  return (
    <>
      <div className={cn(
        "grid grid-cols-[1fr_auto] items-center gap-3 px-4 py-2.5",
        !row.can_edit && "bg-muted/20")}>
        <div className="min-w-0">
          <p className="truncate text-[13px] font-medium">{row.subject_name}</p>
          <p className="truncate font-mono text-[10px] text-muted-foreground">
            {row.teacher_name ?? "no teacher assigned"}
            {row.portion_chapters
              ? ` · ${row.portion_chapters} chapter${row.portion_chapters === 1 ? "" : "s"} in the portion`
              : ""}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {recorded ? (
            <span className="text-right font-mono text-[11px] tabular-nums">
              <span className="text-[13px]">
                {row.avg_pct != null ? `${row.avg_pct}%` : "—"}
              </span>
              <span className="ml-1.5 text-muted-foreground">
                {row.scored}/{row.roster}
              </span>
            </span>
          ) : (
            // Never a 0% and never red — nothing has been claimed about anyone.
            <span className="font-mono text-[10px] text-muted-foreground">
              not entered
            </span>
          )}
          {row.locked ? <Badge tone="success"><Lock className="h-3 w-3" /> locked</Badge> : null}

          {row.can_edit ? (
            <Button size="sm" variant={recorded ? "outline" : "primary"}
              onClick={() => setOpen(true)}>
              {recorded ? "Edit marks" : "Enter marks"}
            </Button>
          ) : recorded ? (
            <Link href={`/students/academics/exams/exam/${row.cycle_id}`}
              className="inline-flex h-8 items-center rounded-full border border-border px-3 text-xs font-medium transition-colors hover:bg-muted">
              View
            </Link>
          ) : (
            <span className="font-mono text-[10px] text-muted-foreground">
              not yours
            </span>
          )}
        </div>
      </div>

      {open ? (
        <Modal open={open} onOpenChange={setOpen}
          title={`${exam.title} · ${row.subject_name}`}
          description="Drop the marked scripts in, or type the marks. The paper is filed under this exam.">
          <ExamCapture classId={classId} examId={row.cycle_id ?? undefined}
            fixedSubjectId={row.subject_id}
            examEventId={exam.exam_event_id}
            defaultName={`${exam.title} · ${row.subject_name}`}
            onSaved={() => { onSaved(); setOpen(false); }} />
        </Modal>
      ) : null}
    </>
  );
}

function ExamPapers({ eventId }: { eventId: string }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["main-exam", eventId],
    queryFn: () => schoolApi.mainExam(eventId),
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["main-exam", eventId] });
    qc.invalidateQueries({ queryKey: ["main-exams"] });
  };

  if (isLoading) return <PageLoading label="Loading the papers…" />;
  if (!data) return null;

  return (
    <div>
      <p className="mb-3 text-[13px] leading-snug text-muted-foreground">
        {data.headline}
      </p>

      <div className="space-y-3">
        {data.classes.map((g) => (
          <section key={g.class_id}
            className="overflow-hidden rounded-xl border border-border bg-card">
            <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-border px-4 py-2.5">
              <span className="text-sm font-semibold">{g.class_label}</span>
              <span className="flex items-center gap-3">
                <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
                  {g.recorded} of {g.total} papers recorded
                </span>
                {/* The report card is the physical artefact this exam produces
                    — one click, and it is the SAME grid Students → Reports
                    renders, never a second version of a child's marks. */}
                <Link href={`/students/academics/reports?class=${g.class_id}`}
                  className="font-mono text-[10px] uppercase tracking-[0.1em] text-primary hover:underline">
                  Report cards
                </Link>
              </span>
            </header>
            <div className="divide-y divide-border">
              {g.subjects.map((row) => (
                <PaperCell key={row.class_subject_id} row={row}
                  classId={g.class_id} exam={data} onSaved={refresh} />
              ))}
            </div>
          </section>
        ))}
        {data.classes.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            No classes to examine here.
          </p>
        ) : null}
      </div>
    </div>
  );
}

// ── the screen ───────────────────────────────────────────────────────────────
export function MainExamBoardView({ yearId }: { yearId: string | null }) {
  const qc = useQueryClient();
  const [picked, setPicked] = useState<string | null>(null);
  const [sheet, setSheet] = useState(false);
  const [editing, setEditing] = useState<MainExamRow | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["main-exams", yearId],
    queryFn: () => schoolApi.mainExams(yearId ?? undefined),
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["main-exams"] });

  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteMainExam(id),
    onSuccess: () => { toast.success("Exam removed"); refresh(); setPicked(null); },
    onError: (e) => showApiError(e, "Could not remove the exam"),
  });

  if (isLoading) return <PageLoading label="Loading exams…" />;
  if (!data) return null;

  const active = data.rows.find((r) => r.exam_event_id === picked)
    ?? data.rows.find((r) => r.state === "running")
    ?? data.rows.find((r) => r.state === "upcoming")
    ?? data.rows[data.rows.length - 1]
    ?? null;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-base font-medium leading-snug">
          {data.headline}
        </p>
        {data.can_edit ? (
          <Button size="sm" variant="outline"
            onClick={() => { setEditing(null); setSheet(true); }}>
            <Plus className="h-4 w-4" /> Add exam
          </Button>
        ) : null}
      </div>

      {/* 1 · the exams themselves */}
      <section className="mb-6 overflow-hidden rounded-xl border border-border bg-card">
        {data.rows.length ? (
          <div className="divide-y divide-border">
            {data.rows.map((r) => {
              const on = active?.exam_event_id === r.exam_event_id;
              return (
                <div key={r.exam_event_id}
                  className={cn("grid grid-cols-[auto_1fr_auto] items-center gap-3 px-4 py-2.5",
                    on && "bg-muted/40")}>
                  <button type="button" onClick={() => setPicked(r.exam_event_id)}
                    className="contents text-left">
                    <ChevronRight className={cn(
                      "h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform",
                      on && "rotate-90")} />
                    <span className="min-w-0">
                      <span className="flex flex-wrap items-baseline gap-1.5">
                        <span className="text-[13px] font-semibold">{r.title}</span>
                        <Badge tone={STATE[r.state]?.tone ?? "neutral"}>
                          {STATE[r.state]?.label ?? r.state}
                        </Badge>
                        {!r.affects_teaching ? (
                          <Badge tone="neutral">teaching continues</Badge>
                        ) : null}
                      </span>
                      <span className="mt-0.5 block truncate font-mono text-[10px] text-muted-foreground">
                        {fmtDay(r.start_date)}
                        {r.end_date !== r.start_date ? ` → ${fmtDay(r.end_date)}` : ""}
                        {" · "}{r.caption}
                      </span>
                    </span>
                  </button>
                  {data.can_edit ? (
                    <span className="flex shrink-0 gap-1">
                      <button type="button" aria-label={`Edit ${r.title}`}
                        onClick={() => { setEditing(r); setSheet(true); }}
                        className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
                        <Pencil className="h-3.5 w-3.5" />
                      </button>
                      <button type="button" aria-label={`Remove ${r.title}`}
                        onClick={() => {
                          if (confirm(`Remove "${r.title}"?`)) remove.mutate(r.exam_event_id);
                        }}
                        className="grid h-7 w-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-danger-soft hover:text-danger">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </span>
                  ) : <span />}
                </div>
              );
            })}
          </div>
        ) : (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">
            <CalendarDays className="mx-auto mb-2 h-6 w-6" />
            {data.can_edit
              ? "No exams on the calendar yet. Add the year's exams and every class's papers hang off them."
              : "No exams have been put on the calendar yet."}
          </p>
        )}
      </section>

      {/* 2 · the picked exam's papers */}
      {active ? (
        <>
          <h2 className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
            {active.title} · papers
          </h2>
          <ExamPapers eventId={active.exam_event_id} />
        </>
      ) : null}

      <ExamSheet open={sheet} onOpenChange={setSheet} yearId={yearId}
        exam={editing} onSaved={refresh} />
    </div>
  );
}
