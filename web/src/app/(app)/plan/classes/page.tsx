"use client";

/**
 * Plan → Classes (V2-P10). The board that answers "is my year sound?".
 *
 * After ingestion the admin has a lot of correct data and no way to see whether it
 * hangs together. This is one row per class and one column per way a year quietly
 * fails: a subject with no teacher, a subject with no syllabus, an empty timetable,
 * an unapproved plan, a forecast already in the red.
 *
 * Every number is derived on read, so fixing something anywhere makes the row go
 * quiet without anyone rebuilding a cache.
 */

import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, BookOpen, CalendarClock, Users } from "lucide-react";
import Link from "next/link";

import { AuthGuard } from "@/components/auth/auth-guard";
import { TeacherLoad } from "@/components/school/teacher-load";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";
import type { ClassRow, Rag } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const RAG_TONE: Record<Rag, "success" | "neutral" | "warning" | "danger"> = {
  green: "success",
  none: "neutral",
  amber: "warning",
  red: "danger",
};
const RAG_LABEL: Record<Rag, string> = {
  green: "on track",
  none: "no plan",
  amber: "slipping",
  red: "behind",
};

function Stat({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>
      {hint ? <p className="mt-0.5 text-[11px] text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

/** The things that make a class quietly wrong. Silence here is the goal. */
function Gaps({ c }: { c: ClassRow }) {
  const gaps: string[] = [];
  if (c.subjects === 0) gaps.push("no subjects");
  if (c.subjects_without_teacher) gaps.push(`${c.subjects_without_teacher} without a teacher`);
  if (c.subjects_without_syllabus) gaps.push(`${c.subjects_without_syllabus} without a syllabus`);
  if (!c.timetable_slots) gaps.push("no timetable");
  if (c.plans_total && c.plans_approved < c.plans_total)
    gaps.push(`${c.plans_total - c.plans_approved} plan(s) unapproved`);

  if (!gaps.length) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-warning">
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
      {gaps.join(" · ")}
    </span>
  );
}

function ClassesInner() {
  const { yearId } = useYear();
  const { data, isLoading } = useQuery({
    queryKey: ["school-overview", yearId],
    queryFn: () => schoolApi.schoolOverview(yearId ?? undefined),
    enabled: !!yearId,
  });

  if (isLoading || !data) {
    return <PageHeader title="Classes" subtitle="Loading…" />;
  }

  const { year } = data;
  const planned = data.classes.reduce((a, c) => a + c.plans_approved, 0);
  const plannable = data.classes.reduce((a, c) => a + c.plans_total, 0);

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <PageHeader title="Classes" subtitle={`${year.label} · everything you set up, in one place`} />
        <YearSwitcher />
      </div>

      <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Classes" value={data.classes.length} />
        <Stat label="Students" value={data.students} />
        <Stat label="Teachers" value={data.teachers} />
        <Stat
          label="Plans approved"
          value={`${planned}/${plannable}`}
          hint={plannable && planned === plannable ? "the year is locked" : "approve to lock the baseline"}
        />
      </div>

      {year.exams > 0 && year.exams_without_portions > 0 ? (
        <div className="mb-6 flex items-start gap-2 rounded-xl border border-border bg-warning-soft/50 px-4 py-3 text-sm text-warning">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            {year.exams_without_portions} of {year.exams} exams have no syllabus portion set, so we
            can&apos;t warn you when a chapter won&apos;t be taught before it.{" "}
            <Link href="/plan" className="font-medium underline underline-offset-2">
              Set them on the Year tab
            </Link>
            .
          </p>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <table className="w-full text-sm">
          <thead className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-4 py-2.5 font-medium">Class</th>
              <th className="px-4 py-2.5 font-medium">Students</th>
              <th className="px-4 py-2.5 font-medium">Subjects</th>
              <th className="px-4 py-2.5 font-medium">Periods</th>
              <th className="px-4 py-2.5 font-medium">Plan</th>
              <th className="px-4 py-2.5 font-medium">Needs attention</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.classes.map((c, i) => (
              <motion.tr
                key={c.class_id}
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.02, 0.2) }}
                className="hover:bg-muted/50"
              >
                <td className="px-4 py-2.5 font-medium">{c.label}</td>
                <td className="px-4 py-2.5 tabular-nums text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <Users className="h-3.5 w-3.5" /> {c.students}
                  </span>
                </td>
                <td className="px-4 py-2.5 tabular-nums text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <BookOpen className="h-3.5 w-3.5" /> {c.subjects}
                  </span>
                </td>
                <td className="px-4 py-2.5 tabular-nums text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <CalendarClock className="h-3.5 w-3.5" /> {c.timetable_slots}/wk
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <Badge tone={RAG_TONE[c.worst_forecast]}>{RAG_LABEL[c.worst_forecast]}</Badge>
                </td>
                <td className={cn("px-4 py-2.5")}>
                  <Gaps c={c} />
                </td>
                <td className="px-4 py-2.5 text-right">
                  <Link
                    href={`/plan/classes/${c.class_id}`}
                    className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                  >
                    Open <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
        {!data.classes.length ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">
            No classes in this year yet.
          </p>
        ) : null}
      </div>

      <div className="mt-6">
        <TeacherLoad />
      </div>
    </div>
  );
}

export default function ClassesPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <ClassesInner />
    </AuthGuard>
  );
}
