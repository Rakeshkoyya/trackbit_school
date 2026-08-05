"use client";

/**
 * Plan → Exams (founder, 2026-08-05) — the school's own exam calendar.
 *
 * Its own tab rather than a third one under Syllabus, because the two questions
 * are different in kind: **Syllabus** and **Exam mapping** are both about
 * chapters (where they are, and which exam examines them); this is about the
 * exams themselves and the marks that come off them.
 *
 * One screen for both roles. An admin adds, edits and removes the exams; a
 * teacher reads the identical list locked and enters marks for her own subject.
 * The server decides both — `can_edit` on the board, `can_edit` per paper — so
 * there is nothing here to branch on, and no second, thinner screen for her that
 * would hide what the school has declared.
 */

import { AuthGuard } from "@/components/auth/auth-guard";
import { MainExamBoardView } from "@/components/school/main-exam-board";
import { YearSwitcher } from "@/components/school/year-switcher";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";

function ExamsInner() {
  const { yearId } = useYear();
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <PageHeader title="Exams"
          subtitle="The exams the school holds, and every class's papers under them" />
        <YearSwitcher />
      </div>
      <MainExamBoardView yearId={yearId} />
    </div>
  );
}

export default function PlanExamsPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <ExamsInner />
    </AuthGuard>
  );
}
