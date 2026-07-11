"use client";

import { useQuery } from "@tanstack/react-query";
import { Camera, ClipboardList, Plus } from "lucide-react";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { NewCycleSheet, ScoreGrid, useClassPick } from "@/components/school/assessments";
import { CaptureReview, useStartCapture } from "@/components/school/score-capture";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";
import type { Cycle } from "@/lib/school-types";

/** Pick the capture target (subject or skill area) and start the photo flow. */
function StartCaptureSheet({ cycle, classId, open, onOpenChange, onStarted }: {
  cycle: Cycle | undefined; classId: string; open: boolean;
  onOpenChange: (v: boolean) => void; onStarted: (id: string) => void;
}) {
  const [target, setTarget] = useState("");
  const isDiagnostic = cycle?.type === "diagnostic";
  const { data: subjects = [] } = useQuery({ queryKey: ["subjects"], queryFn: schoolApi.subjects, enabled: open && !isDiagnostic });
  const { data: skills = [] } = useQuery({ queryKey: ["skills"], queryFn: schoolApi.skillAreas, enabled: open && isDiagnostic });
  const options = isDiagnostic ? skills : (cycle?.subject_id ? subjects.filter((s) => s.id === cycle.subject_id) : subjects);
  const effTarget = options.some((o) => o.id === target) ? target : (options[0]?.id ?? "");
  const start = useStartCapture((id) => { onOpenChange(false); onStarted(id); });

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Scores from photo">
      <div className="space-y-3">
        <p className="text-xs text-muted-foreground">
          Photograph the evaluated papers or your mark register. The system reads the
          names and marks; you review and confirm — nothing is saved until you do.
        </p>
        <div>
          <Label>{isDiagnostic ? "Skill area" : "Subject"}</Label>
          <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
            value={effTarget} onChange={(e) => setTarget(e.target.value)}>
            {options.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}
          </select>
        </div>
        <Button className="w-full" disabled={start.isPending || !effTarget || !cycle}
          onClick={() => start.mutate({
            cycle_id: cycle!.id, class_id: classId,
            ...(isDiagnostic ? { skill_area_id: effTarget } : { subject_id: effTarget }) })}>
          <Camera className="h-4 w-4" /> Start
        </Button>
      </div>
    </Sheet>
  );
}

function ScoresInner() {
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin";
  const { yearId } = useYear();
  const { classes, classId, setClassId } = useClassPick(yearId);
  const [pickedCycle, setPickedCycle] = useState("");
  const [newCycle, setNewCycle] = useState(false);
  const [startCapture, setStartCapture] = useState(false);
  const [activeCapture, setActiveCapture] = useState<string | null>(null);

  const { data: terms = [] } = useQuery({ queryKey: ["terms", yearId], queryFn: () => schoolApi.terms(yearId ?? undefined), enabled: !!yearId });
  const { data: cycles = [] } = useQuery({ queryKey: ["cycles", yearId], queryFn: () => schoolApi.cycles(), enabled: !!yearId });
  const cycleId = cycles.some((c) => c.id === pickedCycle) ? pickedCycle : (cycles[0]?.id ?? "");
  const cycle = cycles.find((c) => c.id === cycleId);
  const termId = terms[0]?.id ?? null;

  // Unfinished photo captures for this cycle+class — resumable in one tap.
  const { data: pending = [] } = useQuery({
    queryKey: ["captures", cycleId, classId],
    queryFn: () => schoolApi.captures({ cycleId, classId }),
    enabled: !!cycleId && !!classId,
    select: (rows) => rows.filter((r) => r.status === "uploaded" || r.status === "parsed"),
  });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <PageHeader title="Scores" subtitle="Diagnostics, unit tests, term exams & daily tests" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <select className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm" value={classId} onChange={(e) => setClassId(e.target.value)}>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
          </select>
        </div>
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select className="rounded-md border border-border bg-card px-2 py-1.5 text-sm" value={cycleId} onChange={(e) => { setPickedCycle(e.target.value); setActiveCapture(null); }}>
          {cycles.length === 0 ? <option value="">No cycles</option> : null}
          {cycles.map((c) => <option key={c.id} value={c.id}>{c.name} ({c.type.replace("_", " ")})</option>)}
        </select>
        {cycleId && classId ? (
          <Button size="sm" variant="outline" onClick={() => setStartCapture(true)}>
            <Camera className="h-4 w-4" /> From photo
          </Button>
        ) : null}
        {canEdit ? <Button size="sm" variant="outline" onClick={() => setNewCycle(true)}><Plus className="h-4 w-4" /> New cycle</Button> : null}
        {pending.map((p) => (
          <button key={p.id} onClick={() => setActiveCapture(p.id)}>
            <Badge tone="warning"><Camera className="h-3 w-3" /> {p.status === "parsed" ? "review pending" : `photo capture (${p.page_count} pages)`}</Badge>
          </button>
        ))}
      </div>

      {activeCapture ? (
        <CaptureReview captureId={activeCapture} onDone={() => setActiveCapture(null)} />
      ) : cycleId && classId ? (
        <ScoreGrid cycleId={cycleId} classId={classId} canVerify={canEdit} />
      ) : (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          <ClipboardList className="mx-auto mb-2 h-6 w-6" /> Create a cycle to record scores.
        </p>
      )}

      <NewCycleSheet open={newCycle} onOpenChange={setNewCycle} termId={termId} yearId={yearId} />
      <StartCaptureSheet cycle={cycle} classId={classId} open={startCapture}
        onOpenChange={setStartCapture} onStarted={setActiveCapture} />
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
