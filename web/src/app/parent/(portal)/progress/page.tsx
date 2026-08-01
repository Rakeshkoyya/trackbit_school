"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { MeterBar } from "@/components/charts";
import { parentApi, type ParentReportSubject } from "@/lib/parent-api";

import { useParentPortal } from "../parent-context";

// V1-6 (`S-51`): the coverage figure is NOT computed here any more. This page
// used to sum `topics_taught / topics_total` in the browser — a definition of
// "syllabus covered" that differed from the admin board's in both numerator and
// denominator, so a parent and a principal could read different percentages for
// the same subject on the same day, and no test could ever have caught it. The
// server now sends one figure from `core.coverage`, measured against the WHOLE
// syllabus, which is the only denominator that cannot go down when the school
// sizes next term's chapters (`S-54`).

function SubjectCard({ s }: { s: ParentReportSubject }) {
  const taught = s.coverage_taught;
  const total = s.coverage_total;
  const latest = s.scores[s.scores.length - 1];
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">{s.subject_name}</h2>
        {s.teacher_name ? (
          <span className="text-xs text-muted-foreground">{s.teacher_name}</span>
        ) : null}
      </div>

      <div className="mt-3 space-y-2.5">
        <div>
          <div className="mb-1 flex justify-between text-xs text-muted-foreground">
            <span>Syllabus covered</span>
            {/* The denominator is stated, always (rule 3). */}
            <span className="tabular-nums">{taught} of {total} topics</span>
          </div>
          <MeterBar
            parts={[
              { value: taught, color: "var(--chart-green)", label: "Covered" },
              { value: Math.max(0, total - taught), color: "var(--muted)", label: "Still to come" },
            ]}
          />
          {/* `S-48` — the chapter name beats the percentage for a parent,
              because it is the thing they can ask their child about at dinner.
              Still no pace, no lag, no "behind" anywhere near this (`D-11`). */}
          {s.latest_chapter ? (
            <p className="mt-1.5 text-xs text-muted-foreground">
              Currently on <span className="font-medium text-foreground">{s.latest_chapter}</span>
              {s.latest_topic ? <> — {s.latest_topic}</> : null}
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
          {s.attendance.pct != null ? (
            <span>
              Attendance <span className="font-medium text-foreground">{s.attendance.pct}%</span>
            </span>
          ) : null}
          <span>
            Homework <span className="font-medium text-foreground">{s.homework_assigned}</span>
            {s.homework_personal > 0 ? ` (+${s.homework_personal} personal)` : ""}
          </span>
          {latest ? (
            <span>
              Last test{" "}
              <span className="font-medium text-foreground">
                {latest.score}/{latest.max_score}
              </span>
            </span>
          ) : null}
        </div>
      </div>
    </section>
  );
}

export default function ParentProgressPage() {
  const { child } = useParentPortal();
  const { data, isLoading } = useQuery({
    queryKey: ["parent", "report", child?.student_id],
    queryFn: () => parentApi.report(child!.student_id),
    enabled: !!child,
  });

  if (!child || isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-4">
      {data.subjects.length ? (
        data.subjects.map((s) => <SubjectCard key={s.subject_name} s={s} />)
      ) : (
        <p className="py-10 text-center text-sm text-muted-foreground">
          No subjects set up for {child.full_name}&apos;s class yet.
        </p>
      )}
    </div>
  );
}
