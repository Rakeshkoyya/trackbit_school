"use client";

/**
 * Exam ↔ syllabus mapping (SY-1).
 *
 * The portion used to be a cut point — "everything up to here" — set from one
 * control buried under the Year calendar. That model cannot say the thing a
 * school says in November: *"Term 1 examines chapters 1, 2, 3 and 5. Chapter 4
 * goes to Term 2."*
 *
 * So a portion is a row of chapter toggles, and the two facts that make ticking
 * them a decision rather than a guess ride on each chip:
 *
 *   · **already examined** — a chapter an earlier exam covers is marked, so
 *     re-examining it is a deliberate press and not something nobody noticed;
 *   · **where it stands** — a chapter that is not even planned before this exam
 *     is dashed, the board's no-record texture, because ticking it is a promise
 *     the calendar cannot currently keep.
 *
 * The verdict beside each subject is the planner's own `exam_fit`, read rather
 * than recomputed, so this screen and the Year tab's panel cannot disagree.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Check, Info } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { ExamMapChapter, ExamMapSubject } from "@/lib/syllabus-types";
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

function ChapterChip({ ch, selected, disabled, onToggle }: {
  ch: ExamMapChapter; selected: boolean; disabled: boolean; onToggle: () => void;
}) {
  const unplanned = ch.status === "not_scheduled";
  return (
    <button type="button" disabled={disabled} onClick={onToggle}
      aria-pressed={selected}
      title={[
        ch.est_periods ? `${ch.est_periods} periods` : "not sized",
        ch.planned_end ? `planned to finish ${fmtDay(ch.planned_end)}` : "not scheduled",
        ch.covered_earlier ? "already examined by an earlier exam" : null,
      ].filter(Boolean).join(" · ")}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
        selected
          ? "border-primary bg-primary text-primary-foreground"
          : unplanned
            // Not on the plan: the no-record texture, never red. Ticking it is
            // a promise the calendar cannot currently keep.
            ? "border-dashed border-border text-muted-foreground hover:border-primary/60"
            : "border-border bg-card text-foreground hover:border-primary/60",
        disabled ? "cursor-not-allowed opacity-60" : "",
      )}>
      {selected ? <Check className="h-3 w-3" /> : null}
      <span className="max-w-[12rem] truncate">{ch.title}</span>
      {ch.est_periods ? (
        <span className={cn("font-mono tabular-nums",
          selected ? "opacity-80" : "text-muted-foreground")}>{ch.est_periods}p</span>
      ) : null}
      {ch.covered_earlier ? (
        <span className={cn("rounded-full px-1 text-[10px]",
          selected ? "bg-primary-foreground/20" : "bg-muted text-muted-foreground")}>
          seen
        </span>
      ) : null}
    </button>
  );
}

function SubjectRow({ examId, subject, canEdit, onSaved }: {
  examId: string; subject: ExamMapSubject; canEdit: boolean; onSaved: () => void;
}) {
  const verdict = VERDICT[subject.verdict];
  const [pending, setPending] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: (unitIds: string[]) => schoolApi.setExamPortionChapters({
      exam_event_id: examId, class_subject_id: subject.class_subject_id,
      unit_ids: unitIds,
    }),
    onSuccess: () => { setPending(null); onSaved(); },
    onError: (e) => { setPending(null); showApiError(e, "Could not save the portion"); },
  });

  const selected = subject.chapters.filter((c) => c.selected).map((c) => c.unit_id);
  const toggle = (unitId: string) => {
    setPending(unitId);
    save.mutate(selected.includes(unitId)
      ? selected.filter((id) => id !== unitId)
      : [...selected, unitId]);
  };

  return (
    <div className="border-b border-border px-3 py-3 last:border-b-0">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <p className="text-sm font-medium">{subject.subject_name}</p>
        <Badge tone={verdict.tone}>{verdict.label}</Badge>
        {subject.verdict !== "no_portion" && subject.verdict !== "unallocated" ? (
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
            {subject.required_periods}p needed
            <span className="px-1 text-muted-foreground/50">of</span>
            {subject.capacity_periods}p before it
          </span>
        ) : null}
        {subject.unsized_topics ? (
          <span className="text-[11px] text-muted-foreground">
            · {subject.unsized_topics} topic{subject.unsized_topics === 1 ? "" : "s"} not sized
          </span>
        ) : null}
        {subject.source === "legacy_prefix" ? (
          <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
            <Info className="h-3 w-3" />
            set as “up to” — tick a chapter to restate it
          </span>
        ) : null}
      </div>
      {subject.chapters.length ? (
        <div className="flex flex-wrap gap-1.5">
          {subject.chapters.map((ch) => (
            <ChapterChip key={ch.unit_id} ch={ch} selected={ch.selected}
              disabled={!canEdit || save.isPending && pending === ch.unit_id}
              onToggle={() => toggle(ch.unit_id)} />
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          No chapters in this subject&apos;s syllabus yet.
        </p>
      )}
    </div>
  );
}

export function ExamSyllabusMap({ classId, canEdit }: {
  classId: string; canEdit: boolean;
}) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["exam-map", classId],
    queryFn: () => schoolApi.examMap(classId),
    enabled: !!classId,
  });
  const [openExam, setOpenExam] = useState<string | null>(null);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["exam-map", classId] });
    // The portion re-scopes every fit verdict hanging off it.
    qc.invalidateQueries({ queryKey: ["exam-fit"] });
    toast.success("Portion saved");
  };

  if (isLoading || !data) {
    return (
      <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
        Working out what each exam examines…
      </p>
    );
  }

  const active = openExam ?? data.exams.find((e) => e.days_to_exam >= 0)?.exam_event_id
    ?? data.exams[0]?.exam_event_id ?? null;

  return (
    <div>
      <p className="mb-4 text-base font-medium">{data.headline}</p>

      {!data.exams.length ? (
        <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
          No exams on the calendar for this year. Add them on Plan → Year, then come
          back and say what each one examines.
        </p>
      ) : (
        <div className="space-y-3">
          {data.exams.map((exam) => {
            const isOpen = exam.exam_event_id === active;
            const past = exam.days_to_exam < 0;
            return (
              <div key={exam.exam_event_id}
                className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                <button type="button"
                  onClick={() => setOpenExam(isOpen ? "" : exam.exam_event_id)}
                  aria-expanded={isOpen}
                  className="flex w-full flex-wrap items-center gap-2 px-3 py-2.5 text-left transition-colors hover:bg-muted/40">
                  <CalendarClock className={cn("h-4 w-4",
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
                  <span className="ml-auto flex gap-1">
                    {exam.subjects.filter((s) => s.verdict === "short").length ? (
                      <Badge tone="danger">
                        {exam.subjects.filter((s) => s.verdict === "short").length} won&apos;t fit
                      </Badge>
                    ) : null}
                    {exam.subjects.filter((s) => s.verdict === "no_portion").length ? (
                      <Badge tone="outline">
                        {exam.subjects.filter((s) => s.verdict === "no_portion").length} unmapped
                      </Badge>
                    ) : null}
                  </span>
                </button>
                {isOpen ? (
                  <div className="border-t border-border">
                    {exam.subjects.map((s) => (
                      <SubjectRow key={s.class_subject_id} examId={exam.exam_event_id}
                        subject={s} canEdit={canEdit} onSaved={invalidate} />
                    ))}
                  </div>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
