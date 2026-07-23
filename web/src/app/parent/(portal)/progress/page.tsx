"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { MeterBar } from "@/components/charts";
import { parentApi, type ParentReportSubject } from "@/lib/parent-api";

import { useParentPortal } from "../parent-context";

function coverage(s: ParentReportSubject) {
  const total = s.chapters.reduce((n, c) => n + c.topics_total, 0);
  const taught = s.chapters.reduce((n, c) => n + c.topics_taught, 0);
  return { total, taught };
}

function SubjectCard({ s }: { s: ParentReportSubject }) {
  const { total, taught } = coverage(s);
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
            <span className="tabular-nums">
              {taught}/{total} topics
            </span>
          </div>
          <MeterBar
            parts={[
              { value: taught, color: "var(--chart-green)", label: "Covered" },
              { value: Math.max(0, total - taught), color: "var(--muted)", label: "Remaining" },
            ]}
          />
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
