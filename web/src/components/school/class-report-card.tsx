"use client";

/**
 * The class report card (V1-8, `D-81` level 1).
 *
 * *"The class version is the same thing for everybody"* — so it is literally
 * the same computation as one child's card, read in one batched pass: students
 * down, exams across, marks in the cells.
 *
 * The rules it inherits, and the reason it is a grid rather than a league table:
 *
 * - **No rank, and no class position.** A position is the one number that
 *   changes a child's year and tells a teacher nothing they can act on. Rows
 *   are in roster order, never sorted by mark.
 * - **Nothing pooled across scale** (`S-114`). Each column says which bucket it
 *   belongs to; there is no row total, because a row total would be exactly the
 *   blended figure this packet removed.
 * - **A blank cell is "did not sit", never a zero** — an empty cell that reads
 *   as nought is how a child absent for the hard paper ends up looking weak.
 * - **Never a band** (P4). This is the surface most likely to be printed.
 */

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { schoolApi } from "@/lib/school-api";

export function ClassReportCard({ classId }: { classId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["class-report-card", classId],
    queryFn: () => schoolApi.classReportCard(classId),
  });

  if (isLoading) return <div className="h-48 animate-pulse rounded-xl bg-muted" />;
  if (!data) return null;
  if (!data.columns.length) {
    return (
      <p className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
        No tests recorded for {data.class_label} yet. Record one and the cards build themselves.
      </p>
    );
  }

  const markOf = (studentId: string, cycleId: string) => {
    const s = data.students.find((x) => x.student_id === studentId);
    for (const subj of s?.subjects ?? []) {
      const hit = subj.exams.find((e) => e.cycle_id === cycleId);
      if (hit) return hit;
    }
    return null;
  };

  return (
    <div className="space-y-3">
      <p className="text-xs text-muted-foreground">
        {data.students.length} students · {data.columns.length} test
        {data.columns.length === 1 ? "" : "s"} · marks only. A blank cell means they did not
        sit that paper — it is not a zero, and there is no row total, because minor tests and
        major exams are never added together.
      </p>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
            <tr>
              <th className="sticky left-0 z-10 bg-muted/40 px-3 py-2">Student</th>
              {data.columns.map((c) => (
                <th key={c.cycle_id} className="px-2 py-2 font-medium">
                  <span className="block whitespace-nowrap text-foreground">{c.name}</span>
                  <span className="block whitespace-nowrap font-normal">
                    {c.subject_name ? `${c.subject_name} · ` : ""}{c.type_label}
                    {c.total_marks ? ` · /${c.total_marks}` : ""}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.students.map((s) => (
              <tr key={s.student_id} className="border-t border-border">
                <td className="sticky left-0 z-10 whitespace-nowrap bg-card px-3 py-1.5 font-medium">
                  <Link href={`/students/${s.student_id}`} className="hover:underline">
                    {s.full_name}
                  </Link>
                  {s.roll_no ? <span className="ml-1.5 text-xs text-muted-foreground">#{s.roll_no}</span> : null}
                </td>
                {data.columns.map((c) => {
                  const m = markOf(s.student_id, c.cycle_id);
                  return (
                    <td key={c.cycle_id} className="px-2 py-1.5 tabular-nums">
                      {m ? (
                        <span>
                          {m.score}
                          <span className="text-xs text-muted-foreground">/{m.max_score}</span>
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
        <Badge tone="neutral">minor tests show movement</Badge>
        <Badge tone="neutral">major exams show standing</Badge>
        <span>Open a student for their own card and the written analysis.</span>
      </div>
    </div>
  );
}
