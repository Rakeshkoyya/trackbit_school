"use client";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ClassSelect, SubjectSelect, SyllabusEditor, useClassSubjectPick } from "@/components/school/plan-shared";
import { YearSwitcher } from "@/components/school/year-switcher";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";

function SyllabusInner() {
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin";
  const { yearId } = useYear();
  const { classes, classId, setClassId, subjects, csId, setCsId } = useClassSubjectPick(yearId);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <PageHeader title="Syllabus" subtitle="Chapters and topics per class-subject" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <ClassSelect classes={classes} classId={classId} onChange={setClassId} />
        </div>
      </div>

      {csId ? (
        <>
          <div className="mb-3 flex items-center gap-2">
            <h2 className="text-sm font-semibold">Subject</h2>
            <SubjectSelect subjects={subjects} csId={csId} onChange={setCsId} />
          </div>
          <SyllabusEditor csId={csId} canEdit={canEdit} />
        </>
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
