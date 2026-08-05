"use client";

/**
 * Students → Academics → Exams (SC-5; redesigned by the founder 2026-08-05).
 *
 * It was a grid of class tiles over a flat feed. Pick a class, land on a
 * capture form, and pick your subject again there — from a dropdown of every
 * subject in the school, most of which are not yours. And the feed was
 * `limit`-capped and unfiltered, so the 31st test of the term was unreachable
 * from any screen.
 *
 * Now: **class, then subject, then record** — and the feed underneath is filtered
 * to that pair and paginated, so "how did 6-B do in Hindi this term" is a
 * question the screen can answer.
 *
 * The scope is the two roles' own:
 *
 *   a teacher   `/planner/my-subjects` — the class-subjects assigned to HER,
 *               which is exactly the set `assert_can_record_subject` now
 *               permits her to write. Offering her a colleague's subject would
 *               be offering a refusal.
 *   an admin    every class, every subject.
 */

import { useQueries, useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { NewCycleSheet } from "@/components/school/assessments";
import { ExamWorkbench, type WorkbenchClass } from "@/components/school/exam-workbench";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

/** An admin's scope: every class, and every subject on it. One query per class,
 *  run together — a school has a dozen or two, not a thousand. */
function useAdminScope(yearId: string | null) {
  const { data: classes = [], isLoading } = useQuery({
    queryKey: ["classes", yearId, "all"],
    queryFn: () => schoolApi.classes(yearId!),
    enabled: !!yearId,
  });
  const subjectQueries = useQueries({
    queries: classes.map((c) => ({
      queryKey: ["class-subjects", c.id],
      queryFn: () => schoolApi.classSubjects(c.id),
    })),
  });
  const rows: WorkbenchClass[] = classes.map((c, i) => ({
    class_id: c.id,
    class_label: `${c.name}${c.section ? `-${c.section}` : ""}`,
    subjects: (subjectQueries[i]?.data ?? [])
      .filter((cs) => cs.subject_id)
      .map((cs) => ({ id: cs.subject_id, label: cs.subject_name ?? "Subject" })),
  }));
  return { rows, isLoading: isLoading || subjectQueries.some((q) => q.isLoading) };
}

/** A teacher's scope: the class-subjects assigned to her, grouped by class. */
function useTeacherScope(yearId: string | null) {
  const { data, isLoading } = useQuery({
    queryKey: ["my-subjects", yearId],
    queryFn: () => schoolApi.mySubjects(yearId ?? undefined),
  });
  const byClass = new Map<string, WorkbenchClass>();
  for (const r of data?.rows ?? []) {
    if (!r.subject_id) continue;
    const entry = byClass.get(r.class_id) ?? {
      class_id: r.class_id, class_label: r.class_label, subjects: [],
    };
    if (!entry.subjects.some((s) => s.id === r.subject_id)) {
      entry.subjects.push({ id: r.subject_id, label: r.subject_name });
    }
    byClass.set(r.class_id, entry);
  }
  return { rows: [...byClass.values()], isLoading };
}

function ExamsInner() {
  const { me } = useAuth();
  const isAdmin = me?.org_role === "admin";
  const { yearId } = useYear();
  const [newCycle, setNewCycle] = useState(false);

  const admin = useAdminScope(isAdmin ? yearId : null);
  const teacher = useTeacherScope(isAdmin ? null : yearId);
  const scope = isAdmin ? admin : teacher;

  const { data: terms = [] } = useQuery({
    queryKey: ["terms", yearId],
    queryFn: () => schoolApi.terms(yearId ?? undefined),
    enabled: !!yearId,
  });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <PageHeader title="Exams"
          subtitle="Record a test for a class and subject, and read every previous one" />
        <div className="flex flex-wrap items-center justify-end gap-2">
          <YearSwitcher />
          {isAdmin ? (
            <Button size="sm" variant="outline" onClick={() => setNewCycle(true)}>
              <Plus className="h-4 w-4" /> New cycle
            </Button>
          ) : null}
        </div>
      </div>

      <ExamWorkbench classes={scope.rows} isLoading={scope.isLoading}
        captureHint="Photograph the marked scripts or type the marks — review, then save."
        emptyScopeText={isAdmin
          ? "No classes in this year yet — set them up in Setup → Academics."
          : "You are not assigned to any subject yet, so there is nothing here to record. Your admin assigns subjects in Setup → Academics."} />

      <NewCycleSheet open={newCycle} onOpenChange={setNewCycle}
        termId={terms[0]?.id ?? null} yearId={yearId} />
    </div>
  );
}

export default function ExamsPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <ExamsInner />
    </AuthGuard>
  );
}
