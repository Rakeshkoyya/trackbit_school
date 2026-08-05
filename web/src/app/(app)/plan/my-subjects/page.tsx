"use client";

/**
 * Plan → My subjects (V1-6 `S-46`, rebuilt for SY-1).
 *
 * Arrives asking: *"Where am I in my own subjects, and what do I do about it?"*
 * The V1-6 screen answered the first half — a list of subjects with a pace chip
 * — and had no answer at all for the second. It now reads top to bottom as one
 * argument:
 *
 *   ① **the shape of her term** — four figures that are about HER, never a
 *      comparison with a colleague. `S-170` holds: no rank, no league table.
 *   ② **the subjects themselves** — the V1-6 pace list, unchanged, because it
 *      is the thing that says what to teach next.
 *   ③ **one subject's chapters**, as the same table the admin reads. One
 *      computation, two renderings.
 *   ④ **Adjust the plan** — the dialog where she moves a chapter and watches
 *      what it does to the gap before the exam.
 *
 * `D-15` throughout: the server scopes every read on `teacher_member_id`, so no
 * other teacher's subject is ever loaded here.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, CheckCircle2, Clock, Layers } from "lucide-react";
import { useMemo, useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BoardSkeleton } from "@/components/insights/shared";
import { PlanTimelineDialog } from "@/components/school/plan-timeline";
import { SubjectPaceList } from "@/components/school/subject-pace-list";
import { SyllabusTable } from "@/components/school/syllabus-table";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";
import type { SyllabusSubjectGroup } from "@/lib/syllabus-types";
import { cn } from "@/lib/utils";

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN",
    { day: "numeric", month: "short" });

/** One figure about her own term. Deliberately not a chart: four numbers with
 *  the words that make them mean something (rule 3). */
function Tile({ icon: Icon, label, value, hint, tone = "neutral" }: {
  icon: typeof Layers;
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "neutral" | "warn" | "good";
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-3.5">
      <div className="flex items-center gap-1.5 text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        <p className="font-mono text-[10px] uppercase tracking-[0.08em]">{label}</p>
      </div>
      <p className={cn("mt-1.5 font-mono text-2xl tabular-nums",
        tone === "warn" ? "text-warning" : tone === "good" ? "text-success" : "")}>
        {value}
      </p>
      {hint ? (
        <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

function MySubjectsInner() {
  const { yearId } = useYear();
  const qc = useQueryClient();
  const [pickedClass, setPickedClass] = useState("");
  const [pickedCs, setPickedCs] = useState("");
  const [adjusting, setAdjusting] = useState<string | null>(null);

  const { data: pace, isLoading: paceLoading } = useQuery({
    queryKey: ["planner", "my-subjects", yearId],
    queryFn: () => schoolApi.mySubjects(yearId ?? undefined),
  });
  const { data: board, isLoading: boardLoading } = useQuery({
    queryKey: ["syllabus-board", "mine", yearId],
    queryFn: () => schoolApi.syllabusBoard({ yearId: yearId ?? undefined }),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["syllabus-board"] });
    qc.invalidateQueries({ queryKey: ["planner", "my-subjects"] });
  };

  // The picker's options come from the board she already has — no second read,
  // so the two can never disagree about which subjects are hers.
  const classes = board?.classes ?? [];
  const classId = classes.some((c) => c.class_id === pickedClass)
    ? pickedClass : (classes[0]?.class_id ?? "");
  const subjects = classes.find((c) => c.class_id === classId)?.subjects ?? [];
  // Default to a subject that HAS chapters. A class teacher sees every subject
  // of her homeroom, alphabetically, so the plain first-item default landed on
  // English — a subject nobody has entered a syllabus for — and the screen
  // opened on "no chapters recorded yet" for a teacher with two full syllabuses.
  const csId = subjects.some((s) => s.class_subject_id === pickedCs)
    ? pickedCs
    : (subjects.find((s) => s.chapters.length)?.class_subject_id
      ?? subjects[0]?.class_subject_id ?? "");
  const subject = subjects.find((s) => s.class_subject_id === csId);

  // Not memoised: it is a two-field object rebuilt from data the render already
  // holds, and memoising it made `subject` a dependency the compiler could not
  // prove stable.
  const scoped = board && subject
    ? {
      ...board,
      classes: [{
        class_id: subject.class_id, label: subject.class_label, subjects: [subject],
      }],
    }
    : null;

  const totals = useMemo(() => {
    if (!board) return null;
    const rows = board.classes.flatMap((c) => c.subjects.flatMap((s) => s.chapters));
    const next = rows
      .filter((r) => r.status !== "completed" && r.planned_start)
      .sort((a, b) => a.planned_start!.localeCompare(b.planned_start!))[0];
    return {
      // Deliberately named against the BOARD, not against `pace.rows`. A class
      // teacher's board carries every subject of her homeroom, so this count is
      // legitimately larger than "your subjects" in the headline above — and two
      // unexplained subject counts on one screen is the defect BA-1 had to fix
      // twice. The tile says which set it is counting.
      subjects: board.classes.reduce((n, c) => n + c.subjects.length, 0),
      classCount: board.classes.length,
      classLabel: board.classes.length === 1 ? board.classes[0].label : null,
      total: board.chapters_total,
      completed: board.completed,
      overdue: board.overdue,
      unscheduled: board.not_scheduled,
      next,
    };
  }, [board]);

  if (paceLoading || boardLoading || !pace || !board) {
    return (
      <>
        <PageHeader title="My subjects" subtitle="Where you are, and what to teach next." />
        <BoardSkeleton />
      </>
    );
  }

  return (
    <div>
      <PageHeader title="My subjects" subtitle="Where you are, and what to teach next." />

      {/* ① Lead with a sentence, not a number (rule 3). */}
      <p className="mb-4 text-base font-medium">{pace.headline}</p>

      {totals ? (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Tile icon={Layers} label="Chapters"
            value={`${totals.completed}/${totals.total}`}
            hint={`finished across ${totals.subjects} subject${totals.subjects === 1 ? "" : "s"} in `
              + (totals.classLabel ?? `${totals.classCount} classes`)} />
          <Tile icon={Clock} label="Overdue" value={totals.overdue}
            tone={totals.overdue ? "warn" : "good"}
            hint={totals.overdue
              ? "planned to finish by now, and not finished"
              : "nothing has slipped past its planned end"} />
          {/* Not scheduled is a STATE, never a warning — a school that plans
              term by term has these all April (V2-P11). */}
          <Tile icon={CheckCircle2} label="Not scheduled" value={totals.unscheduled}
            hint={totals.unscheduled
              ? "recorded but not on the plan yet — normal, not a problem"
              : "every chapter has dates"} />
          <Tile icon={CalendarClock} label="Up next"
            value={totals.next
              ? <span className="text-base leading-tight">{totals.next.title}</span>
              : <span className="text-base text-muted-foreground">—</span>}
            hint={totals.next?.planned_start
              ? `from ${fmtDay(totals.next.planned_start)}`
              : "nothing scheduled ahead"} />
        </div>
      ) : null}

      {/* ② The pace list — what to teach next, per subject. */}
      <div className="mb-6">
        <h2 className="mb-2 font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
          Your subjects
        </h2>
        <SubjectPaceList
          rows={pace.rows}
          emptyText="You are not assigned to any class-subject yet. Ask the office to add you to one." />
      </div>

      {/* ③ One subject's chapters, and ④ the way to change them. */}
      {classes.length ? (
        <div>
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground">
              Chapter by chapter
            </h2>
            <div className="flex flex-wrap items-center gap-2">
              <select value={classId} onChange={(e) => setPickedClass(e.target.value)}
                aria-label="Class"
                className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm">
                {classes.map((c) => (
                  <option key={c.class_id} value={c.class_id}>{c.label}</option>
                ))}
              </select>
              <select value={csId} onChange={(e) => setPickedCs(e.target.value)}
                aria-label="Subject"
                className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm">
                {subjects.map((s) => (
                  <option key={s.class_subject_id} value={s.class_subject_id}>
                    {s.subject_name}
                  </option>
                ))}
              </select>
              {csId ? (
                <button type="button" onClick={() => setAdjusting(csId)}
                  className="inline-flex h-8 items-center gap-1.5 rounded-full border border-primary bg-primary px-3 text-xs font-medium text-primary-foreground transition-opacity hover:opacity-90">
                  <CalendarClock className="h-3.5 w-3.5" /> Adjust the plan
                </button>
              ) : null}
            </div>
          </div>
          {scoped ? (
            <SyllabusTable board={scoped} canEdit onChanged={refresh}
              onAdjust={(s: SyllabusSubjectGroup) => setAdjusting(s.class_subject_id)} />
          ) : null}
        </div>
      ) : null}

      <PlanTimelineDialog csId={adjusting} open={!!adjusting}
        onOpenChange={(v) => { if (!v) setAdjusting(null); }}
        onSaved={refresh} />
    </div>
  );
}

export default function MySubjectsPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MySubjectsInner />
    </AuthGuard>
  );
}
