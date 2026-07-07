"use client";

import { useQuery } from "@tanstack/react-query";
import { ClipboardList, Plus } from "lucide-react";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { NewCycleSheet, ScoreGrid, useClassPick } from "@/components/school/assessments";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

function ScoresInner() {
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin";
  const { yearId } = useYear();
  const { classes, classId, setClassId } = useClassPick(yearId);
  const [pickedCycle, setPickedCycle] = useState("");
  const [newCycle, setNewCycle] = useState(false);

  const { data: terms = [] } = useQuery({ queryKey: ["terms", yearId], queryFn: () => schoolApi.terms(yearId ?? undefined), enabled: !!yearId });
  const { data: cycles = [] } = useQuery({ queryKey: ["cycles", yearId], queryFn: () => schoolApi.cycles(), enabled: !!yearId });
  const cycleId = cycles.some((c) => c.id === pickedCycle) ? pickedCycle : (cycles[0]?.id ?? "");
  const termId = terms[0]?.id ?? null;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <PageHeader title="Scores" subtitle="Diagnostics, unit tests & term exams" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <select className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm" value={classId} onChange={(e) => setClassId(e.target.value)}>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
          </select>
        </div>
      </div>

      <div className="mb-3 flex items-center gap-2">
        <select className="rounded-md border border-border bg-card px-2 py-1.5 text-sm" value={cycleId} onChange={(e) => setPickedCycle(e.target.value)}>
          {cycles.length === 0 ? <option value="">No cycles</option> : null}
          {cycles.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.type})</option>)}
        </select>
        {canEdit ? <Button size="sm" variant="outline" onClick={() => setNewCycle(true)}><Plus className="h-4 w-4" /> New cycle</Button> : null}
      </div>
      {cycleId && classId ? <ScoreGrid cycleId={cycleId} classId={classId} canVerify={canEdit} /> : (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          <ClipboardList className="mx-auto mb-2 h-6 w-6" /> Create a cycle to record scores.
        </p>
      )}
      <NewCycleSheet open={newCycle} onOpenChange={setNewCycle} termId={termId} yearId={yearId} />
    </div>
  );
}

export default function ScoresPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <ScoresInner />
    </AuthGuard>
  );
}
