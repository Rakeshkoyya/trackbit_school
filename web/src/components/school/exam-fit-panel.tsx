"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ClassSelect } from "@/components/school/plan-shared";
import { Badge } from "@/components/ui/badge";
import { schoolApi } from "@/lib/school-api";
import type { ExamFitSubject, ExamFitVerdict } from "@/lib/school-types";

/**
 * Live "does the syllabus fit before each exam?" feedback (V2-P12).
 *
 * Everything here is recomputed server-side on each fetch, so the caller just
 * invalidates ["exam-fit"] whenever exam dates, portions, syllabus sizes or
 * allocations change and the verdicts update in place. Used on Plan → Year and
 * inside the wizard's calendar step.
 */

const TONE: Record<ExamFitVerdict, "success" | "warning" | "danger" | "neutral"> = {
  short: "danger",
  tight: "warning",
  fits: "success",
  surplus: "neutral",
  no_portion: "neutral",
  unallocated: "warning",
};

const LABEL: Record<ExamFitVerdict, string> = {
  short: "won't fit",
  tight: "manageable",
  fits: "perfect",
  surplus: "spare time",
  no_portion: "no portion set",
  unallocated: "no periods/week",
};

function fitDetail(s: ExamFitSubject): string {
  if (s.verdict === "no_portion") return "map the exam's portion to see the fit";
  if (s.verdict === "unallocated") return "set periods/week on the class first";
  const base = `needs ${s.required_periods}p · has ~${Math.round(s.capacity_periods)}p`;
  return s.unsized_topics > 0 ? `${base} · ${s.unsized_topics} unsized` : base;
}

const fmt = (d: string) =>
  new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" });

export function ExamFitPanel({ yearId }: { yearId: string }) {
  const [picked, setPicked] = useState("");
  const { data: classes = [] } = useQuery({
    queryKey: ["classes", yearId],
    queryFn: () => schoolApi.classes(yearId),
    enabled: !!yearId,
  });
  const classId = classes.some((c) => c.id === picked) ? picked : (classes[0]?.id ?? "");
  const { data: fit } = useQuery({
    queryKey: ["exam-fit", classId],
    queryFn: () => schoolApi.examFit(classId),
    enabled: !!classId,
  });

  if (!classId) return null;

  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Exam fit — will the portion finish in time?</h2>
        <ClassSelect classes={classes} classId={classId} onChange={setPicked} />
      </div>

      {!fit || fit.exams.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
          No exams on this year&apos;s calendar yet — paint an exam block to see the fit.
        </p>
      ) : (
        <div className="space-y-3">
          {fit.exams.map((ex) => (
            <div key={ex.exam_event_id} className="rounded-lg border border-border bg-card p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <p className="text-sm font-medium">{ex.title}</p>
                <span className="text-xs text-muted-foreground">
                  {fmt(ex.start_date)} – {fmt(ex.end_date)}
                </span>
                <span className="text-xs text-muted-foreground">
                  · {ex.teaching_days_in_gap} teaching days before it
                </span>
                <div className="flex-1" />
                <Badge tone={ex.days_to_exam < 0 ? "neutral" : ex.days_to_exam <= 14 ? "warning" : "primary"}>
                  {ex.days_to_exam < 0 ? "done" : `in ${ex.days_to_exam}d`}
                </Badge>
              </div>
              <div className="space-y-1.5">
                {ex.subjects.map((s) => (
                  <div key={s.class_subject_id} className="flex flex-wrap items-center gap-2 text-sm">
                    <span className="min-w-28 font-medium">{s.subject_name}</span>
                    <Badge tone={TONE[s.verdict]}>{LABEL[s.verdict]}</Badge>
                    <span className="text-xs text-muted-foreground">{fitDetail(s)}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
