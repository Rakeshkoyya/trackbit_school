"use client";

import { useQuery } from "@tanstack/react-query";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ClassSelect, SubjectSelect, SyllabusEditor, useClassSubjectPick } from "@/components/school/plan-shared";
import { YearSwitcher } from "@/components/school/year-switcher";
import { PageHeader } from "@/components/ui/page-header";
import { PageLoading } from "@/components/ui/page-loading";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

function SyllabusInner() {
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin";
  const { yearId } = useYear();
  const { classes, classId, setClassId, subjects, csId, setCsId, loading } = useClassSubjectPick(yearId);
  // All the year's terms, not just those that already have chapters — a new chapter
  // has to be assignable to an empty term.
  const { data: terms = [] } = useQuery({
    queryKey: ["terms", yearId], queryFn: () => schoolApi.terms(yearId!), enabled: !!yearId,
  });

  return (
    <div>
      {/* One selector row: year · class · subject, all in the same line. */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <PageHeader title="Syllabus" subtitle="Chapters and topics per class-subject" />
        <div className="flex flex-wrap items-center gap-2">
          <YearSwitcher />
          <ClassSelect classes={classes} classId={classId} onChange={setClassId} />
          <SubjectSelect subjects={subjects} csId={csId} onChange={setCsId} />
        </div>
      </div>

      {loading ? (
        <PageLoading label="Loading the syllabus…" />
      ) : csId ? (
        <SyllabusEditor csId={csId} canEdit={canEdit} terms={terms} />
      ) : (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          No subjects on this class yet — add classes & subjects in Setup.
        </p>
      )}
    </div>
  );
}

export default function SyllabusPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <SyllabusInner />
    </AuthGuard>
  );
}
