"use client";

import { AuthGuard } from "@/components/auth/auth-guard";
import { useClassPick } from "@/components/school/assessments";
import { ClassAnalytics } from "@/components/school/class-analytics";
import { YearSwitcher } from "@/components/school/year-switcher";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";

function TrendsInner() {
  const { yearId } = useYear();
  const { classes, classId, setClassId } = useClassPick(yearId);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <PageHeader title="Trends" subtitle="How this class is moving, subject by subject" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <select className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm" value={classId} onChange={(e) => setClassId(e.target.value)}>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
          </select>
        </div>
      </div>
      {classId ? <ClassAnalytics classId={classId} /> : null}
    </div>
  );
}

export default function TrendsPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <TrendsInner />
    </AuthGuard>
  );
}
