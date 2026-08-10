"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Sparkles, Upload } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BellEditor } from "@/components/school/bell-editor";
import { ClassSelect, useClassSubjectPick } from "@/components/school/plan-shared";
import { TeacherWeekGrid, TimetableGrid } from "@/components/school/timetable-grid";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { appApi } from "@/lib/app-api";
import { BLOCK_KINDS, DEFAULT_BLOCK_KIND, blockLabel, captureFor } from "@/lib/day-shape";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { TimetableBlock } from "@/lib/school-types";

/** Create or edit a block — a period that is not a subject (TT-2).
 *
 *  A block carries no weekdays or times of its own: the grid says when it runs
 *  (`D-113`). What it needs from the admin is what it *is* (the kind, which
 *  decides what the teacher is asked to capture), who may run it, and whether
 *  it is only for hostellers — which is the whole day-scholar / hosteller split
 *  in one checkbox.
 */
function BlockSheet({ open, onOpenChange, editing }: {
  open: boolean; onOpenChange: (v: boolean) => void; editing: TimetableBlock | null;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [kind, setKind] = useState<string>(DEFAULT_BLOCK_KIND);
  const [hostellersOnly, setHostellersOnly] = useState(false);
  const [staff, setStaff] = useState<Set<string>>(new Set());
  const [seeded, setSeeded] = useState<string | null>(null);

  // Reset the form whenever the sheet opens on a different block — adjusted
  // during render (React's documented pattern) rather than in an effect.
  const formKey = open ? (editing?.id ?? "new") : null;
  if (formKey !== seeded) {
    setSeeded(formKey);
    if (open) {
      setName(editing?.name ?? "");
      setKind(editing?.kind ?? DEFAULT_BLOCK_KIND);
      setHostellersOnly(editing?.hostellers_only ?? false);
      setStaff(new Set(editing?.staff_member_ids ?? []));
    }
  }

  const { data: membersRes } = useQuery({
    queryKey: ["members"], queryFn: appApi.members, enabled: open });
  const teachers = (membersRes?.members ?? []).filter((m) => m.status === "active" && m.member_id);

  const done = (msg: string) => {
    qc.invalidateQueries({ queryKey: ["timetable-blocks"] });
    qc.invalidateQueries({ queryKey: ["timetable"] });
    toast.success(msg);
    onOpenChange(false);
  };
  const body = () => ({
    name: name.trim(), kind, hostellers_only: hostellersOnly,
    staff_member_ids: [...staff],
  });
  const create = useMutation({
    mutationFn: () => schoolApi.createBlock(body()),
    onSuccess: () => done("Block added"),
    onError: (e) => showApiError(e, "Could not add the block"),
  });
  const update = useMutation({
    mutationFn: () => schoolApi.updateBlock(editing!.id, body()),
    onSuccess: () => done("Block saved"),
    onError: (e) => showApiError(e, "Could not save the block"),
  });
  const cap = captureFor(kind);
  const asks = [
    cap.roll && "attendance",
    cap.homeworkCheck && "homework checking",
    cap.classLog && "a class log",
    cap.studentLogs && "per-student notes",
    cap.memories && "photos",
  ].filter(Boolean) as string[];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}
           title={editing ? "Edit block" : "New block"}>
      <div className="space-y-4">
        <label className="block text-sm">
          <span className="mb-1 block text-muted-foreground">Name</span>
          <Input value={name} placeholder="e.g. Homework class, AI class, Games"
                 onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="block text-sm">
          <span className="mb-1 block text-muted-foreground">What kind of period is it?</span>
          <select value={kind} onChange={(e) => setKind(e.target.value)}
                  className="h-9 w-full rounded-md border border-border bg-card px-2 text-sm">
            {BLOCK_KINDS.map((k) => (
              <option key={k} value={k}>{blockLabel(k)}</option>
            ))}
          </select>
          <span className="mt-1 block text-xs text-muted-foreground">
            The teacher will be asked for {asks.join(", ")}.
          </span>
        </label>
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" checked={hostellersOnly} className="mt-0.5"
                 onChange={(e) => setHostellersOnly(e.target.checked)} />
          <span>
            Hostellers only
            <span className="block text-xs text-muted-foreground">
              Day scholars go home; only hostellers appear on the roll.
            </span>
          </span>
        </label>
        <div className="text-sm">
          <span className="mb-1 block text-muted-foreground">Who can take it</span>
          <div className="max-h-56 space-y-1 overflow-y-auto rounded-md border border-border p-2">
            {teachers.map((t) => (
              <label key={t.member_id} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox" checked={staff.has(t.member_id!)}
                  onChange={(e) => setStaff((prev) => {
                    const next = new Set(prev);
                    if (e.target.checked) next.add(t.member_id!); else next.delete(t.member_id!);
                    return next;
                  })}
                />
                {t.name}
              </label>
            ))}
            {teachers.length === 0 ? (
              <p className="text-xs text-muted-foreground">No active staff yet.</p>
            ) : null}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Anyone ticked can open it and record the day — so assembly or yoga can
            be taken by whoever is free. Leave empty and only you can.
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          Which classes and when it runs come from the grid — put the block in a
          cell and that class joins it.
        </p>
        <Button className="w-full" disabled={!name.trim() || create.isPending || update.isPending}
                onClick={() => (editing ? update.mutate() : create.mutate())}>
          {editing ? "Save block" : "Add block"}
        </Button>
      </div>
    </Sheet>
  );
}

function BlocksPanel() {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<TimetableBlock | null>(null);
  const { data: blocks = [] } = useQuery({
    queryKey: ["timetable-blocks"], queryFn: schoolApi.blocks });
  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteBlock(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["timetable-blocks"] });
      qc.invalidateQueries({ queryKey: ["timetable"] });
      toast.success("Block removed");
    },
    onError: (e) => showApiError(e, "Could not remove the block"),
  });

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm text-muted-foreground">
          A block is a period that is not a subject — homework class, games, an
          extra course, assembly. Build it here, then drop it into the grid.
        </p>
        <Button size="sm" onClick={() => { setEditing(null); setOpen(true); }}>
          <Plus className="h-4 w-4" /> New block
        </Button>
      </div>
      {blocks.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          No blocks yet.
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {blocks.map((b) => (
            <li key={b.id} className="flex flex-wrap items-center gap-2 px-3 py-2.5">
              <div className="min-w-40 flex-1">
                <p className="text-sm font-medium">
                  {b.name}
                  {!b.active ? (
                    <span className="ml-1.5 text-xs text-muted-foreground">· archived</span>
                  ) : null}
                </p>
                <p className="text-xs text-muted-foreground">
                  {b.kind_label}
                  {b.hostellers_only ? " · hostellers only" : ""}
                  {b.slot_count
                    ? ` · ${b.slot_count} period${b.slot_count === 1 ? "" : "s"} on the grid`
                    : " · not on the grid yet"}
                  {b.roster_count ? ` · ${b.roster_count} student${b.roster_count === 1 ? "" : "s"}` : ""}
                </p>
                {b.staff_names.length ? (
                  <p className="text-xs text-muted-foreground/80">{b.staff_names.join(", ")}</p>
                ) : null}
              </div>
              <Button size="sm" variant="outline"
                      onClick={() => { setEditing(b); setOpen(true); }}>Edit</Button>
              <Button size="sm" variant="outline" disabled={remove.isPending}
                      onClick={() => remove.mutate(b.id)}>Remove</Button>
            </li>
          ))}
        </ul>
      )}
      <BlockSheet open={open} onOpenChange={setOpen} editing={editing} />
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

function GenerateSheet({ yearId, open, onOpenChange }: { yearId: string; open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const [preview, setPreview] = useState<import("@/lib/school-types").TimetableGenerate | null>(null);

  const run = useMutation({
    mutationFn: (apply: boolean) => schoolApi.timetableGenerate({ academic_year_id: yearId, apply }),
    onSuccess: (res) => {
      if (res.applied) {
        qc.invalidateQueries({ queryKey: ["timetable"] });
        toast.success(`Timetable generated for ${res.classes} class${res.classes === 1 ? "" : "es"}`);
        setPreview(null);
        onOpenChange(false);
      } else {
        setPreview(res);
      }
    },
    onError: (e) => showApiError(e, "Could not generate"),
  });

  const issues = [...(preview?.skipped ?? []), ...(preview?.unplaced ?? [])];
  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) setPreview(null); onOpenChange(v); }} title="Generate full timetable">
      {!preview ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Fills every class of this year in one pass from each subject&apos;s periods/week —
            no teacher is ever double-booked. You preview before anything changes.
          </p>
          <Button className="w-full" disabled={run.isPending} onClick={() => run.mutate(false)}>
            {run.isPending ? "Generating…" : "Preview"}
          </Button>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm">
            <span className="font-medium">{preview.cells.length}</span> periods across{" "}
            <span className="font-medium">{preview.classes}</span> class{preview.classes === 1 ? "" : "es"}.
          </p>
          {issues.length > 0 ? (
            <div className="max-h-48 space-y-1 overflow-y-auto rounded-md border border-warning/40 bg-warning/5 p-2">
              {issues.map((i, n) => (
                <p key={n} className="text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{i.class_label} {i.subject_name}</span> — {i.detail}
                </p>
              ))}
            </div>
          ) : (
            <p className="text-sm text-success">Every subject placed. No conflicts.</p>
          )}
          <p className="text-xs text-muted-foreground">
            Applying replaces the current grid of every class in this year (history is kept).
          </p>
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={() => setPreview(null)}>Back</Button>
            <Button className="flex-1" disabled={run.isPending} onClick={() => run.mutate(true)}>
              {run.isPending ? "Applying…" : "Apply to all classes"}
            </Button>
          </div>
        </div>
      )}
    </Sheet>
  );
}

const WEEKDAY = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

/** The clash check, finally on screen (V1-13).
 *
 *  `TimetableService` has had a deterministic teacher-clash validator since
 *  V2-P1 and `/timetable/validate` returned its verdict to nobody — so the one
 *  thing the grid can be *wrong* about was invisible. It is school-wide on
 *  purpose: a clash is always between two classes, so checking only the class
 *  on screen would report half of them and hide the other half.
 *
 *  §11 still holds — there is no solver here. This names the cell and the two
 *  classes and leaves the fix to the person who knows which one moves.
 */
function ClashBanner() {
  const { data: clashes = [] } = useQuery({
    queryKey: ["timetable-clashes"],
    queryFn: schoolApi.validateTimetable,
  });
  if (clashes.length === 0) return null;
  return (
    <div className="mb-3 rounded-lg border border-warning/40 bg-warning-soft px-3 py-2.5">
      <p className="text-sm font-medium text-warning">
        {clashes.length === 1
          ? "One teacher is in two rooms at once"
          : `${clashes.length} periods put a teacher in two rooms at once`}
      </p>
      <ul className="mt-1.5 space-y-0.5">
        {clashes.slice(0, 6).map((c, i) => (
          <li key={i} className="text-xs text-muted-foreground">
            <span className="font-medium text-foreground">{c.teacher_name ?? "A teacher"}</span>
            {" · "}{WEEKDAY[c.weekday] ?? `Day ${c.weekday}`} period {c.period_no}
            {" · "}{c.class_labels.join(" and ")}
          </li>
        ))}
      </ul>
      {clashes.length > 6 ? (
        <p className="mt-1 text-xs text-muted-foreground">…and {clashes.length - 6} more</p>
      ) : null}
    </div>
  );
}

function TimetableAdmin() {
  const { yearId } = useYear();
  const { classes, classId, setClassId } = useClassSubjectPick(yearId);
  const qc = useQueryClient();
  const [importOpen, setImportOpen] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [tab, setTab] = useState<"grid" | "timings" | "blocks">("grid");

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
        <PageHeader
          title="Timetable"
          subtitle="The shape of the day, and what runs in each period"
        />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          {tab === "grid" ? (
            <ClassSelect classes={classes} classId={classId} onChange={setClassId} />
          ) : null}
        </div>
      </div>

      <div className="mb-4 flex gap-1 border-b border-border">
        {([
          ["grid", "Grid"],
          ["timings", "School timings"],
          ["blocks", "Blocks"],
        ] as const).map(([key, label]) => (
          <button
            key={key} type="button" onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              tab === key
                ? "border-primary font-medium text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "timings" ? (
        yearId ? <BellEditor yearId={yearId} /> : (
          <p className="text-sm text-muted-foreground">Pick an academic year first.</p>
        )
      ) : tab === "blocks" ? (
        <BlocksPanel />
      ) : classId ? (
        <>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <div className="flex-1" />
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}><Upload className="h-4 w-4" /> Import</Button>
            <Button size="sm" variant="outline" disabled={draft.isPending} onClick={() => draft.mutate()}>
              <Sparkles className="h-4 w-4" /> Draft for me
            </Button>
            <Button size="sm" onClick={() => setGenerateOpen(true)}>
              <Sparkles className="h-4 w-4" /> Generate all classes
            </Button>
          </div>
          <ClashBanner />
          <TimetableGrid classId={classId} canEdit />
          <ImportSheet classId={classId} open={importOpen} onOpenChange={setImportOpen} />
          {yearId ? <GenerateSheet yearId={yearId} open={generateOpen} onOpenChange={setGenerateOpen} /> : null}
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
