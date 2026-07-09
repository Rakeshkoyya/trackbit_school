"use client";

/**
 * Tie an exam to the syllabus it examines (V2-P7).
 *
 * This is the small control that earns the planner its keep. Once an exam knows
 * which chapters it covers, `generate` can say the one sentence an admin actually
 * needs in June: "Simple equations is not planned to finish before Term 1 Exam."
 *
 * The portion is stored as a single cut point — every topic up to and including
 * `upto_topic_id`, in syllabus order — so re-ordering the syllabus re-scopes it
 * for free and nothing can go stale.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { CalendarEvent, SchoolClass } from "@/lib/school-types";

export function ExamPortions({
  exams,
  classes,
}: {
  exams: CalendarEvent[];
  classes: SchoolClass[];
}) {
  const qc = useQueryClient();
  const [examId, setExamId] = useState("");
  const [pickedClass, setClassId] = useState("");

  const exam = exams.find((e) => e.id === examId) ?? exams[0];
  const classId = pickedClass || classes[0]?.id || "";

  const { data: css } = useQuery({
    queryKey: ["class-subjects", classId],
    queryFn: () => schoolApi.classSubjects(classId),
    enabled: !!classId,
  });
  const { data: portions } = useQuery({
    queryKey: ["exam-portions"],
    queryFn: () => schoolApi.examPortions(),
  });

  const set = useMutation({
    mutationFn: (b: { class_subject_id: string; upto_topic_id: string }) =>
      schoolApi.setExamPortion({ exam_event_id: exam!.id, ...b }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["exam-portions"] });
      qc.invalidateQueries({ queryKey: ["wizard"] });
      toast.success("Portion set");
    },
    onError: (e) => showApiError(e, "Could not set the portion"),
  });

  if (!exams.length) {
    return (
      <p className="rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted-foreground">
        Mark an exam on the calendar and you can say which chapters it covers.
      </p>
    );
  }

  return (
    <div className="space-y-3 rounded-xl border border-border bg-card p-3">
      <div>
        <h3 className="text-sm font-semibold">What does each exam cover?</h3>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Optional, but it&apos;s how we warn you when a chapter won&apos;t be taught in time.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <select
          aria-label="Exam"
          value={exam?.id ?? ""}
          onChange={(e) => setExamId(e.target.value)}
          className="h-10 rounded-md border border-input bg-background px-2 text-sm"
        >
          {exams.map((e) => (
            <option key={e.id} value={e.id}>
              {e.title}
            </option>
          ))}
        </select>
        <select
          aria-label="Class"
          value={classId}
          onChange={(e) => setClassId(e.target.value)}
          className="h-10 rounded-md border border-input bg-background px-2 text-sm"
        >
          {classes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
              {c.section ? `-${c.section}` : ""}
            </option>
          ))}
        </select>
      </div>

      <ul className="space-y-1.5">
        {css?.map((cs) => (
          <SubjectPortion
            key={cs.id}
            csId={cs.id}
            subject={cs.subject_name ?? "Subject"}
            current={portions?.find((p) => p.exam_event_id === exam?.id && p.class_subject_id === cs.id)?.upto_topic_id}
            saving={set.isPending}
            onPick={(topicId) => set.mutate({ class_subject_id: cs.id, upto_topic_id: topicId })}
          />
        ))}
        {!css?.length ? (
          <li className="text-xs text-muted-foreground">This class has no subjects yet.</li>
        ) : null}
      </ul>
    </div>
  );
}

function SubjectPortion({
  csId,
  subject,
  current,
  saving,
  onPick,
}: {
  csId: string;
  subject: string;
  current?: string;
  saving: boolean;
  onPick: (topicId: string) => void;
}) {
  const { data: units } = useQuery({
    queryKey: ["syllabus", csId],
    queryFn: () => schoolApi.syllabus(csId),
  });

  // Flatten to syllabus order — the cut point is an index into this list.
  const topics = useMemo(
    () => (units ?? []).flatMap((u) => u.topics.map((t) => ({ id: t.id, label: `${u.title} · ${t.title}` }))),
    [units],
  );

  return (
    <li className="flex items-center justify-between gap-2">
      <span className="w-28 shrink-0 truncate text-sm">{subject}</span>
      {topics.length ? (
        <div className="flex min-w-0 flex-1 items-center gap-1.5">
          <select
            aria-label={`Portion for ${subject}`}
            value={current ?? ""}
            disabled={saving}
            onChange={(e) => e.target.value && onPick(e.target.value)}
            className="h-9 min-w-0 flex-1 rounded-md border border-input bg-background px-2 text-xs"
          >
            <option value="">Up to…</option>
            {topics.map((t) => (
              <option key={t.id} value={t.id}>
                {t.label}
              </option>
            ))}
          </select>
          {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" /> : null}
        </div>
      ) : (
        <span className="text-xs text-muted-foreground">No syllabus yet</span>
      )}
    </li>
  );
}
