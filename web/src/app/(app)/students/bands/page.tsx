"use client";

import { useQuery } from "@tanstack/react-query";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BandBoard, useClassPick } from "@/components/school/assessments";
import { YearSwitcher } from "@/components/school/year-switcher";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

function BandsInner() {
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin";
  const { yearId } = useYear();
  const { classes, classId, setClassId } = useClassPick(yearId);
  const { data: terms = [] } = useQuery({ queryKey: ["terms", yearId], queryFn: () => schoolApi.terms(yearId ?? undefined), enabled: !!yearId });
  const termId = terms[0]?.id ?? null;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <PageHeader title="Bands" subtitle="Private support tiers & interventions" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <select className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm" value={classId} onChange={(e) => setClassId(e.target.value)}>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
          </select>
        </div>
      </div>
      {classId ? <BandBoard classId={classId} termId={termId} canEdit={canEdit} /> : null}
    </div>
  );
}

export default function BandsPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <BandsInner />
    </AuthGuard>
  );
}
