"use client";

/**
 * Students → Academics → Reports (founder, 2026-08-05).
 *
 * The class's report cards, in one grid: every child down the side, every exam
 * across the top, the mark in the cell. It is `D-81`'s **level 1** — numbers
 * only, no narrative and, deliberately, **no band** (P4): this is the surface
 * most likely to be printed and handed to a family, and a support tier must
 * never leave the staff room.
 *
 * Three things it will not do, each on purpose:
 *
 *   · **No overall average across the top.** Minor and major do not pool
 *     (`S-114`), so one "class average" column would have to add a 5-mark slip
 *     test to an 80-mark final. Each child's two figures ride in their own
 *     columns, each carrying its denominator (`S-118`).
 *   · **A child who did not sit an exam gets a dash, not a zero.** Absent from
 *     the paper is not nought out of eighty, and a table that renders it as one
 *     drags an average down for a fact nobody recorded.
 *   · **No ranking.** `S-170`'s rule, and the exam report's own: named rows
 *     against a stated criterion, never a position in a list.
 *
 * The per-child version — the same figures with the analysis over them — is
 * `/students/[id]`, one click through a name.
 */

import { useQuery } from "@tanstack/react-query";
import { FileText } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { EmptyState } from "@/components/ui/empty-state";
import { PageLoading } from "@/components/ui/page-loading";
import { useYear } from "@/contexts/year-context";
import { useAuth } from "@/contexts/auth-context";
import { schoolApi } from "@/lib/school-api";
import type { ReportCard, ScaleFigure } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const chip = (active: boolean) =>
  cn("whitespace-nowrap rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
    active ? "border-primary bg-primary text-primary-foreground"
      : "border-border text-muted-foreground hover:bg-muted hover:text-foreground");

function FigureCell({ figures, scale }: { figures: ScaleFigure[]; scale: string }) {
  const f = figures.find((x) => x.scale === scale);
  if (!f || f.avg_pct == null) {
    return <span className="text-muted-foreground">—</span>;
  }
  return (
    <span className="tabular-nums" title={f.sentence}>
      {f.avg_pct}%
      <span className="ml-1 text-[11px] text-muted-foreground">
        /{f.tests_held}
      </span>
    </span>
  );
}

function ReportGrid({ classId }: { classId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["class-report-card", classId],
    queryFn: () => schoolApi.classReportCard(classId),
  });

  if (isLoading) return <PageLoading />;
  if (!data || data.students.length === 0) {
    return (
      <EmptyState icon={FileText} title="No marks recorded yet"
        body="Record an exam on the Exams tab and every child's card fills itself — nobody types a report." />
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border shadow-sm">
      <div className="flex flex-wrap items-baseline gap-2 border-b border-border bg-card px-3 py-2">
        <p className="text-sm font-semibold">{data.class_label}</p>
        <span className="text-xs text-muted-foreground">as of {data.as_of}</span>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm" style={{ minWidth: 520 + data.columns.length * 90 }}>
          <thead>
            <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
              <th className="sticky left-0 z-10 bg-muted/40 px-3 py-2 font-medium">Student</th>
              {data.columns.map((c) => (
                <th key={c.cycle_id} className="px-3 py-2 text-right font-medium">
                  <span className="block truncate" title={`${c.name} · ${c.type_label}`}>
                    {c.name}
                  </span>
                  <span className="block text-[10px] font-normal">
                    {c.subject_name ?? "—"}
                    {c.total_marks ? ` · /${c.total_marks}` : ""}
                  </span>
                </th>
              ))}
              <th className="px-3 py-2 text-right font-medium">Major</th>
              <th className="px-3 py-2 text-right font-medium">Minor</th>
            </tr>
          </thead>
          <tbody>
            {data.students.map((s: ReportCard) => {
              const marks = new Map(
                s.subjects.flatMap((sub) => sub.exams.map((e) => [e.cycle_id, e])));
              return (
                <tr key={s.student_id}
                  className="border-b border-border/60 bg-card last:border-0 hover:bg-muted/40">
                  <td className="sticky left-0 z-10 bg-card px-3 py-2">
                    <Link href={`/students/${s.student_id}`}
                      className="font-medium hover:underline">{s.full_name}</Link>
                    {s.roll_no ? (
                      <span className="ml-1.5 text-[11px] text-muted-foreground">
                        {s.roll_no}
                      </span>
                    ) : null}
                  </td>
                  {data.columns.map((c) => {
                    const m = marks.get(c.cycle_id);
                    return (
                      <td key={c.cycle_id} className="px-3 py-2 text-right tabular-nums">
                        {/* Absent from the paper is a dash. A zero here would be
                            a mark nobody gave. */}
                        {m ? `${m.score}` : <span className="text-muted-foreground">—</span>}
                      </td>
                    );
                  })}
                  <td className="px-3 py-2 text-right">
                    <FigureCell figures={s.figures} scale="major" />
                  </td>
                  <td className="px-3 py-2 text-right">
                    <FigureCell figures={s.figures} scale="minor" />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Reports() {
  const { me } = useAuth();
  const { yearId } = useYear();
  const [classId, setClassId] = useState<string | null>(null);
  const { data: classes = [] } = useQuery({
    queryKey: ["classes", yearId, me?.org_role !== "admin"],
    queryFn: () => schoolApi.classes(yearId ?? undefined, me?.org_role !== "admin"),
    enabled: !!yearId,
  });
  const active = classId ?? classes[0]?.id ?? null;

  return (
    <div>
      <div className="mb-4">
        <h1 className="text-2xl font-semibold tracking-tight">Reports</h1>
        <p className="text-sm text-muted-foreground">
          Every child&apos;s marks in one grid. Open a name for their full report.
        </p>
      </div>

      {classes.length === 0 ? (
        <p className="text-sm text-muted-foreground">No classes are assigned to you yet.</p>
      ) : (
        <>
          <div className="mb-4 flex flex-wrap gap-1.5">
            {classes.map((c) => (
              <button key={c.id} type="button" className={chip(c.id === active)}
                onClick={() => setClassId(c.id)}>
                {c.name}{c.section ? `-${c.section}` : ""}
              </button>
            ))}
          </div>
          {active ? <ReportGrid classId={active} /> : null}
        </>
      )}
    </div>
  );
}

export default function AcademicsReportsPage() {
  return (
    <AuthGuard>
      <Reports />
    </AuthGuard>
  );
}
