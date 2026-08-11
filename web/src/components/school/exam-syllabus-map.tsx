"use client";

/**
 * Exam ↔ syllabus mapping (SY-2) — one subject, two ways round.
 *
 * A portion is a SET of chapters: *"Term 1 examines chapters 1, 2, 3 and 5.
 * Chapter 4 goes to Term 2."* SY-1 established that and drew it as a wall of
 * chips, every exam of a class expanded over every subject. That is a lot of
 * ticking and not much reading, and the two questions a school actually asks
 * point in opposite directions:
 *
 *   **"which exam covers this chapter?"**  → the chapter is the row  (by chapter)
 *   **"what is in the half-yearly?"**      → the exam is the table   (by exam)
 *
 * Neither is derivable from the other by looking, so both are drawn, and the
 * toggle at the top is the whole navigation. Underneath they are one fact —
 * `ExamPortion` — and one write, so they cannot drift.
 *
 * Two rules kept from SY-1, because they are what make ticking a box a decision
 * rather than a guess:
 *
 *   · a chapter an EARLIER exam already covers is marked, so re-examining it is
 *     a deliberate press and not something nobody noticed;
 *   · a chapter that is not even planned before this exam is drawn in the
 *     no-record texture, because ticking it is a promise the calendar cannot
 *     currently keep.
 *
 * **Chapter order is syllabus order, everywhere.** The server returns chapters
 * by `position` and nothing here re-sorts them — not even "selected first" —
 * because a portion read out of the book's order cannot be checked against the
 * book.
 *
 * The verdict beside each exam is the planner's own `exam_fit`, read rather
 * than recomputed, so this screen and the Year tab cannot disagree.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarClock, Check, ChevronDown, ChevronRight, Info, Pencil, X,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type {
  ExamMap, ExamMapChapter, ExamMapExam, ExamMapSubject,
} from "@/lib/syllabus-types";
import { cn } from "@/lib/utils";

const VERDICT: Record<ExamMapSubject["verdict"],
  { label: string; tone: "success" | "warning" | "danger" | "neutral" | "outline" }> = {
  fits: { label: "Fits", tone: "success" },
  surplus: { label: "Room to spare", tone: "success" },
  tight: { label: "Tight", tone: "warning" },
  short: { label: "Won't fit", tone: "danger" },
  no_portion: { label: "No portion set", tone: "outline" },
  unallocated: { label: "No periods/week", tone: "outline" },
};

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN",
    { day: "numeric", month: "short" });

/** The picked subject's slice of one exam, or nothing if it has none. */
const sliceOf = (exam: ExamMapExam, csId: string): ExamMapSubject | undefined =>
  exam.subjects.find((s) => s.class_subject_id === csId);

/** One shared write for both views: replace this (exam, subject) portion. */
function usePortionWrite(classId: string, csId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { examId: string; unitIds: string[] }) =>
      schoolApi.setExamPortionChapters({
        exam_event_id: v.examId, class_subject_id: csId, unit_ids: v.unitIds,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-map", classId] });
      // The portion re-scopes every fit verdict hanging off it.
      qc.invalidateQueries({ queryKey: ["exam-fit"] });
      toast.success("Portion saved");
    },
    onError: (e) => showApiError(e, "Could not save the portion"),
  });
}

function ExamHeadline({ exam, slice }: {
  exam: ExamMapExam; slice: ExamMapSubject | undefined;
}) {
  const past = exam.days_to_exam < 0;
  const verdict = slice ? VERDICT[slice.verdict] : null;
  return (
    <>
      <CalendarClock className={cn("h-4 w-4 shrink-0",
        past ? "text-muted-foreground" : "text-primary")} />
      <span className="text-sm font-semibold">{exam.title}</span>
      <span className="font-mono text-xs tabular-nums text-muted-foreground">
        {fmtDay(exam.start_date)}
        {exam.end_date !== exam.start_date ? `–${fmtDay(exam.end_date)}` : ""}
      </span>
      <span className="text-xs text-muted-foreground">
        {past ? "already sat"
          : exam.days_to_exam === 0 ? "today"
            : `in ${exam.days_to_exam} days · ${exam.teaching_days_in_gap} teaching days before it`}
      </span>
      {verdict ? <Badge tone={verdict.tone}>{verdict.label}</Badge> : null}
      {slice && slice.verdict !== "no_portion" && slice.verdict !== "unallocated" ? (
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {slice.required_periods}p needed
          <span className="px-1 text-muted-foreground/50">of</span>
          {slice.capacity_periods}p before it
        </span>
      ) : null}
    </>
  );
}

// ── view 1: the chapter is the row ───────────────────────────────────────────
/**
 * Beside each chapter, the exams that examine it.
 *
 * The control is a dropdown of every exam with the current ones ticked, because
 * a chapter can legitimately be in more than one — a chapter in the half-yearly
 * is usually in the finals too — and a single-choice `<select>` would quietly
 * make that unsayable.
 */
function ExamPicker({ chapter, exams, csId, classId }: {
  chapter: ExamMapChapter; exams: ExamMapExam[]; csId: string; classId: string;
}) {
  const [open, setOpen] = useState(false);
  const save = usePortionWrite(classId, csId);

  const inExam = (e: ExamMapExam) =>
    !!sliceOf(e, csId)?.chapters.find((c) => c.unit_id === chapter.unit_id)?.selected;
  const chosen = exams.filter(inExam);

  const toggle = (e: ExamMapExam) => {
    const slice = sliceOf(e, csId);
    if (!slice) return;
    const now = slice.chapters.filter((c) => c.selected).map((c) => c.unit_id);
    save.mutate({
      examId: e.exam_event_id,
      unitIds: now.includes(chapter.unit_id)
        ? now.filter((id) => id !== chapter.unit_id)
        : [...now, chapter.unit_id],
    });
  };

  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-label={`Exams examining ${chapter.title}`}
        className="flex w-full flex-wrap items-center gap-1 rounded-md border border-transparent px-1.5 py-1 text-left transition-colors hover:border-border hover:bg-card">
        {chosen.length ? chosen.map((e) => (
          <span key={e.exam_event_id}
            className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
            {e.title}
          </span>
        )) : (
          // Never blank and never red: an unmapped chapter is a decision nobody
          // has made yet, not one made badly.
          <span className="text-[11px] text-muted-foreground">not in any exam</span>
        )}
        <ChevronDown className="ml-auto h-3 w-3 shrink-0 text-muted-foreground" />
      </button>
      {open ? (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 top-full z-50 mt-1 w-64 rounded-lg border border-border bg-card p-1 shadow-lg">
            {exams.map((e) => {
              const on = inExam(e);
              return (
                <button key={e.exam_event_id} type="button" onClick={() => toggle(e)}
                  disabled={save.isPending}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted">
                  <span className={cn(
                    "grid h-4 w-4 shrink-0 place-items-center rounded border",
                    on ? "border-primary bg-primary text-primary-foreground"
                      : "border-border")}>
                    {on ? <Check className="h-3 w-3" /> : null}
                  </span>
                  <span className="min-w-0 flex-1 truncate">{e.title}</span>
                  <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                    {fmtDay(e.start_date)}
                  </span>
                </button>
              );
            })}
          </div>
        </>
      ) : null}
    </div>
  );
}

const BY_CHAPTER_COLS = "2.5rem minmax(12rem,1.6fr) 4.5rem 7rem minmax(11rem,1fr)";

function ByChapter({ data, csId, canEdit }: {
  data: ExamMap; csId: string; canEdit: boolean;
}) {
  // Any exam's slice carries the full chapter list in syllabus order — the
  // portion is which of them are ticked, not which of them exist.
  const chapters = data.exams
    .map((e) => sliceOf(e, csId)?.chapters)
    .find((c) => c && c.length) ?? [];

  if (!chapters.length) {
    return (
      <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
        This subject has no chapters yet. Record them on Plan → Syllabus first.
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="overflow-x-auto" style={{ contain: "layout inline-size" }}>
        <div className="min-w-[46rem]">
          <div className="grid gap-2 border-b border-border px-3 py-2"
            style={{ gridTemplateColumns: BY_CHAPTER_COLS }}>
            {["#", "Chapter", "Periods", "Planned to", "Examined by"].map((h) => (
              <div key={h}
                className="font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                {h}
              </div>
            ))}
          </div>
          {chapters.map((ch, i) => (
            <div key={ch.unit_id}
              className="grid items-center gap-2 border-b border-border px-3 py-1.5 transition-colors last:border-b-0 hover:bg-muted/25"
              style={{ gridTemplateColumns: BY_CHAPTER_COLS }}>
              <span className="font-mono text-xs tabular-nums text-muted-foreground">
                {i + 1}
              </span>
              <span className="truncate text-sm" title={ch.title}>{ch.title}</span>
              <span className={cn("font-mono text-xs tabular-nums",
                ch.est_periods == null ? "text-warning" : "text-muted-foreground")}>
                {ch.est_periods ?? "not sized"}
              </span>
              <span className={cn("font-mono text-xs tabular-nums",
                ch.status === "not_scheduled"
                  ? "text-muted-foreground/70" : "text-muted-foreground")}>
                {ch.planned_end ? fmtDay(ch.planned_end) : "not scheduled"}
              </span>
              {canEdit ? (
                <ExamPicker chapter={ch} exams={data.exams} csId={csId}
                  classId={data.class_id} />
              ) : (
                <span className="text-[11px] text-muted-foreground">
                  {data.exams.filter((e) => sliceOf(e, csId)?.chapters
                    .find((c) => c.unit_id === ch.unit_id)?.selected)
                    .map((e) => e.title).join(", ") || "not in any exam"}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── view 2: the exam is the table ────────────────────────────────────────────
const BY_EXAM_COLS = "2.5rem minmax(12rem,1.7fr) 4.5rem 8rem 6rem";

/**
 * One exam's table.
 *
 * **View mode shows the portion**: only the chapters that are in it, which is
 * what the exam actually is and what gets read out to a class. **Edit mode
 * shows the whole syllabus with checkboxes**, because deciding a portion means
 * looking at everything you could have included, not only what you already did.
 *
 * The edit button is per table, not per screen: portions are decided one exam
 * at a time, and a global edit mode would arm every checkbox on the page.
 */
function ExamTable({ exam, csId, classId, canEdit, defaultOpen }: {
  exam: ExamMapExam; csId: string; classId: string; canEdit: boolean;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [editing, setEditing] = useState(false);
  const save = usePortionWrite(classId, csId);
  const slice = sliceOf(exam, csId);

  if (!slice) return null;

  const selected = slice.chapters.filter((c) => c.selected);
  const shown = editing ? slice.chapters : selected;

  const toggle = (unitId: string) => {
    const now = selected.map((c) => c.unit_id);
    save.mutate({
      examId: exam.exam_event_id,
      unitIds: now.includes(unitId)
        ? now.filter((id) => id !== unitId) : [...now, unitId],
    });
  };

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <div className="flex flex-wrap items-center gap-2 px-3 py-2.5">
        <button type="button" onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="flex min-w-0 flex-1 flex-wrap items-center gap-2 text-left">
          {open ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
          <ExamHeadline exam={exam} slice={slice} />
        </button>
        <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
          {selected.length} of {slice.chapters.length} chapters
        </span>
        {canEdit && open ? (
          <Button size="sm" variant={editing ? "primary" : "outline"}
            onClick={() => setEditing((e) => !e)}>
            {editing ? <><X className="h-3.5 w-3.5" /> Done</>
              : <><Pencil className="h-3.5 w-3.5" /> Edit</>}
          </Button>
        ) : null}
      </div>

      {slice.source === "legacy_prefix" ? (
        <p className="flex items-center gap-1 border-t border-border px-3 py-1.5 text-[11px] text-muted-foreground">
          <Info className="h-3 w-3 shrink-0" />
          Set as “up to” — tick a chapter to restate it as a set.
        </p>
      ) : null}

      {open ? (
        <div className="border-t border-border">
          {shown.length ? (
            <div className="overflow-x-auto" style={{ contain: "layout inline-size" }}>
              <div className="min-w-[42rem]">
                <div className="grid gap-2 border-b border-border px-3 py-1.5"
                  style={{ gridTemplateColumns: BY_EXAM_COLS }}>
                  {[editing ? "In" : "#", "Chapter", "Periods", "Planned to", "Status"]
                    .map((h) => (
                      <div key={h}
                        className="font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
                        {h}
                      </div>
                    ))}
                </div>
                {shown.map((ch, i) => {
                  const unplanned = ch.status === "not_scheduled";
                  return (
                    <div key={ch.unit_id}
                      className={cn(
                        "grid items-center gap-2 border-b border-border px-3 py-1.5 last:border-b-0",
                        editing ? "cursor-pointer hover:bg-muted/40" : "hover:bg-muted/20")}
                      style={{ gridTemplateColumns: BY_EXAM_COLS }}
                      onClick={editing ? () => toggle(ch.unit_id) : undefined}>
                      {editing ? (
                        <span className={cn(
                          "grid h-4 w-4 place-items-center rounded border",
                          ch.selected
                            ? "border-primary bg-primary text-primary-foreground"
                            : "border-border")}
                          role="checkbox" aria-checked={ch.selected}
                          aria-label={`${ch.title} in ${exam.title}`}>
                          {ch.selected ? <Check className="h-3 w-3" /> : null}
                        </span>
                      ) : (
                        <span className="font-mono text-xs tabular-nums text-muted-foreground">
                          {i + 1}
                        </span>
                      )}
                      <span className="truncate text-sm" title={ch.title}>
                        {ch.title}
                        {ch.covered_earlier ? (
                          <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground"
                            title="An earlier exam already covers this chapter">
                            seen
                          </span>
                        ) : null}
                      </span>
                      <span className={cn("font-mono text-xs tabular-nums",
                        ch.est_periods == null ? "text-warning" : "text-muted-foreground")}>
                        {ch.est_periods ?? "not sized"}
                      </span>
                      <span className="font-mono text-xs tabular-nums text-muted-foreground">
                        {ch.planned_end ? fmtDay(ch.planned_end) : "—"}
                      </span>
                      {/* Not on the plan before this exam: the no-record
                          texture, never red. Ticking it is a promise the
                          calendar cannot currently keep. */}
                      <span className={cn("text-[11px]",
                        unplanned ? "text-muted-foreground/70" : "text-muted-foreground")}>
                        {unplanned ? "not scheduled" : ch.status.replace("_", " ")}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <p className="px-3 py-8 text-center text-sm text-muted-foreground">
              {slice.chapters.length
                ? canEdit
                  ? "Nothing in this exam yet — press Edit and tick the chapters it examines."
                  : "Nothing has been mapped to this exam yet."
                : "This subject has no chapters yet."}
            </p>
          )}
          {slice.unsized_topics ? (
            <p className="border-t border-border px-3 py-1.5 text-[11px] text-muted-foreground">
              {slice.unsized_topics} topic{slice.unsized_topics === 1 ? "" : "s"} not
              sized — the fit above is worked out from the ones that are.
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

// ── the screen ───────────────────────────────────────────────────────────────
export type ExamMapView = "chapter" | "exam";

export function ExamSyllabusMap({ classId, csId, view, canEdit }: {
  classId: string; csId: string; view: ExamMapView; canEdit: boolean;
}) {
  const { data, isLoading } = useQuery({
    queryKey: ["exam-map", classId],
    queryFn: () => schoolApi.examMap(classId),
    enabled: !!classId,
  });

  if (isLoading || !data) {
    return (
      <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
        Working out what each exam examines…
      </p>
    );
  }

  if (!data.exams.length) {
    return (
      <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
        No exams on the calendar for this year. Add them on Plan → Exams, then
        come back and say what each one examines.
      </p>
    );
  }

  if (!csId || !data.exams.some((e) => sliceOf(e, csId))) {
    return (
      <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
        Pick a subject above to map its chapters onto these exams.
      </p>
    );
  }

  // The one that is next opens by default — the exam somebody is here about.
  const nextId = (data.exams.find((e) => e.days_to_exam >= 0) ?? data.exams[0])
    .exam_event_id;

  return (
    <div>
      <p className="mb-4 text-base font-medium">{data.headline}</p>
      {view === "chapter" ? (
        <ByChapter data={data} csId={csId} canEdit={canEdit} />
      ) : (
        <div className="space-y-3">
          {data.exams.map((exam) => (
            <ExamTable key={exam.exam_event_id} exam={exam} csId={csId}
              classId={data.class_id} canEdit={canEdit}
              defaultOpen={exam.exam_event_id === nextId} />
          ))}
        </div>
      )}
    </div>
  );
}
