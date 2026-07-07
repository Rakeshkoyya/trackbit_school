"use client";

import { AuthGuard } from "@/components/auth/auth-guard";
import { TrendsView, useClassPick } from "@/components/school/assessments";
import { YearSwitcher } from "@/components/school/year-switcher";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";

function TrendsInner() {
  const { yearId } = useYear();
  const { classes, classId, setClassId } = useClassPick(yearId);

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <PageHeader title="Trends" subtitle="Subject-wise progress across cycles" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <select className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm" value={classId} onChange={(e) => setClassId(e.target.value)}>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
          </select>
        </div>
      </div>
      {classId ? <TrendsView classId={classId} /> : null}
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
