"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sparkles, Upload } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ClassSelect, useClassSubjectPick } from "@/components/school/plan-shared";
import { TeacherWeekGrid, TimetableGrid } from "@/components/school/timetable-grid";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

function PeriodsControl({ yearId }: { yearId: string }) {
  const qc = useQueryClient();
  const { data: cfg } = useQuery({ queryKey: ["period-config", yearId], queryFn: () => schoolApi.periodConfig(yearId) });
  const [val, setVal] = useState("");
  const save = useMutation({
    mutationFn: (n: number) => schoolApi.setPeriodConfig({
      academic_year_id: yearId, periods_per_day: n, period_times: cfg?.period_times ?? [] }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["period-config", yearId] }); qc.invalidateQueries({ queryKey: ["timetable"] }); toast.success("Periods/day updated"); },
    onError: (e) => showApiError(e, "Could not update"),
  });
  const current = cfg?.periods_per_day ?? 8;
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className="text-muted-foreground">Periods/day</span>
      <Input className="h-8 w-16" type="number" min={1} max={16}
        value={val === "" ? String(current) : val}
        onChange={(e) => setVal(e.target.value)} />
      <Button size="sm" variant="outline" disabled={save.isPending || val === "" || Number(val) === current}
        onClick={() => save.mutate(Number(val))}>Save</Button>
    </div>
  );
}

function ImportSheet({ classId, open, onOpenChange }: { classId: string; open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [cells, setCells] = useState<{ weekday: number; period_no: number; class_subject_id: string }[] | null>(null);
  const analyze = useMutation({
    mutationFn: (file: File) => schoolApi.timetableImportAnalyze(classId, file),
    onSuccess: (res) => setCells(res.cells.filter((c) => c.class_subject_id).map((c) => ({
      weekday: c.weekday, period_no: c.period_no, class_subject_id: c.class_subject_id! }))),
    onError: (e) => showApiError(e, "Could not read the file"),
  });
  const commit = useMutation({
    mutationFn: () => schoolApi.timetableImportCommit({ class_id: classId, cells: cells! }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["timetable", classId] }); toast.success("Timetable imported"); setCells(null); onOpenChange(false); },
    onError: (e) => showApiError(e, "Import failed"),
  });
  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) setCells(null); onOpenChange(v); }} title="Import timetable">
      {!cells ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Upload a photo or xlsx of the existing timetable — it&apos;s parsed into a grid you confirm before it applies.
          </p>
          <input type="file" accept=".xlsx,image/*"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) analyze.mutate(f); }}
            className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-2 file:text-primary-foreground" />
          {analyze.isPending ? <p className="text-sm text-muted-foreground">Reading…</p> : null}
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm"><span className="font-medium">{cells.length}</span> periods detected. Apply to this class&apos;s grid?</p>
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={() => setCells(null)}>Back</Button>
            <Button className="flex-1" disabled={commit.isPending} onClick={() => commit.mutate()}>
              {commit.isPending ? "Applying…" : `Apply ${cells.length}`}
            </Button>
          </div>
        </div>
      )}
    </Sheet>
  );
}

function TimetableAdmin() {
  const { yearId } = useYear();
  const { classes, classId, setClassId } = useClassSubjectPick(yearId);
  const qc = useQueryClient();
  const [importOpen, setImportOpen] = useState(false);

  const draft = useMutation({
    mutationFn: () => schoolApi.timetableDraft(classId),
    onSuccess: async (res) => {
      if (!res.enabled) { toast.message(res.message); return; }
      const cells = res.cells.filter((c) => c.class_subject_id).map((c) => ({
        weekday: c.weekday, period_no: c.period_no, class_subject_id: c.class_subject_id! }));
      await schoolApi.timetableImportCommit({ class_id: classId, cells });
      qc.invalidateQueries({ queryKey: ["timetable", classId] });
      toast.success(res.unresolved.length ? `Draft applied · ${res.unresolved.length} conflicts to fix` : "Draft applied");
    },
    onError: (e) => showApiError(e, "Could not draft"),
  });

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <PageHeader title="Timetable" subtitle="Weekly period grid — tap a cell to assign a subject" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          <ClassSelect classes={classes} classId={classId} onChange={setClassId} />
        </div>
      </div>

      {classId ? (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            {yearId ? <PeriodsControl yearId={yearId} /> : null}
            <div className="flex-1" />
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}><Upload className="h-4 w-4" /> Import</Button>
            <Button size="sm" variant="outline" disabled={draft.isPending} onClick={() => draft.mutate()}>
              <Sparkles className="h-4 w-4" /> Draft for me
            </Button>
          </div>
          <TimetableGrid classId={classId} canEdit />
          <ImportSheet classId={classId} open={importOpen} onOpenChange={setImportOpen} />
        </>
      ) : (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          Add classes & subjects in Setup first.
        </p>
      )}
    </div>
  );
}

function TimetableTeacher() {
  return (
    <div>
      <div className="mb-4">
        <PageHeader title="My timetable" subtitle="Your week, period by period" />
      </div>
      <TeacherWeekGrid />
    </div>
  );
}

function TimetableInner() {
  const { me } = useAuth();
  return me?.org_role === "admin" ? <TimetableAdmin /> : <TimetableTeacher />;
}

export default function TimetablePage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <TimetableInner />
    </AuthGuard>
  );
}
