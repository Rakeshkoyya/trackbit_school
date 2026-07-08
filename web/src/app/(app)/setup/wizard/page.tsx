"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, PartyPopper, Plus, Sparkles, Wand2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { ClassSubject, SchoolClass, WizardProgress, WizardState } from "@/lib/school-types";

const STEPS = [
  "Academic year", "Exam calendar", "School timings", "Classes & subjects",
  "Syllabus", "Teachers", "Students", "Timetable", "Generate plan",
];

function done(p: WizardProgress, step: number): boolean {
  switch (step) {
    case 1: return p.has_year;
    case 2: return true; // optional
    case 3: return p.has_timings;
    case 4: return p.class_subjects > 0;
    case 5: return p.syllabus_topics > 0;
    case 6: return p.teachers > 0;
    case 7: return p.students > 0;
    case 8: return p.timetable_slots > 0;
    case 9: return p.plans_total > 0 && p.plans_approved >= p.plans_total;
    default: return false;
  }
}

function useYears() {
  return useQuery({ queryKey: ["academic-years"], queryFn: schoolApi.years });
}

// ── step panels ───────────────────────────────────────────────────────────────
function YearStep() {
  const qc = useQueryClient();
  const { data: years } = useYears();
  const [f, setF] = useState({ label: "", start_date: "", end_date: "" });
  const create = useMutation({
    mutationFn: async () => {
      const y = await schoolApi.createYear(f);
      await schoolApi.activateYear(y.id);
      return y;
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["academic-years"] }); qc.invalidateQueries({ queryKey: ["wizard"] }); toast.success("Year created"); setF({ label: "", start_date: "", end_date: "" }); },
    onError: (e) => showApiError(e, "Could not create year"),
  });
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Set the academic year’s dates. Working weekdays and terms can be tuned in Academics.</p>
      {years?.map((y) => <div key={y.id} className="rounded-lg border border-border px-3 py-2 text-sm">{y.label} · {y.start_date} → {y.end_date} {y.is_active ? <Badge tone="success">active</Badge> : null}</div>)}
      <div className="grid gap-2 sm:grid-cols-3">
        <Input placeholder="2026-27" value={f.label} onChange={(e) => setF({ ...f, label: e.target.value })} />
        <Input type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} />
        <Input type="date" value={f.end_date} onChange={(e) => setF({ ...f, end_date: e.target.value })} />
      </div>
      <Button onClick={() => create.mutate()} disabled={create.isPending || !f.label || !f.start_date || !f.end_date}>
        <Plus className="h-4 w-4" /> Create & activate
      </Button>
    </div>
  );
}

function TimingsStep() {
  const qc = useQueryClient();
  const { data: years } = useYears();
  const active = years?.find((y) => y.is_active) ?? years?.[0];
  const [ppd, setPpd] = useState(8);
  const save = useMutation({
    mutationFn: () => schoolApi.setPeriodConfig({
      academic_year_id: active!.id, periods_per_day: ppd,
      period_times: Array.from({ length: ppd }, (_, i) => ({
        start: `${String(9 + i).padStart(2, "0")}:00`, end: `${String(9 + i).padStart(2, "0")}:45`, kind: "period",
      })),
    }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["wizard"] }); toast.success("Timings saved"); },
    onError: (e) => showApiError(e, "Could not save timings"),
  });
  if (!active) return <p className="text-sm text-muted-foreground">Create an academic year first.</p>;
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">How many periods per day? A default schedule is generated — refine it in Academics later.</p>
      <div className="flex items-center gap-2">
        <Label>Periods/day</Label>
        <Input type="number" className="w-20" value={ppd} min={1} max={12} onChange={(e) => setPpd(Number(e.target.value) || 1)} />
        <Button onClick={() => save.mutate()} disabled={save.isPending}>Save timings</Button>
      </div>
    </div>
  );
}

function ClassesStep() {
  const qc = useQueryClient();
  const { data: years } = useYears();
  const active = years?.find((y) => y.is_active) ?? years?.[0];
  const { data: classes } = useQuery({ queryKey: ["classes", active?.id], queryFn: () => schoolApi.classes(active?.id), enabled: !!active });
  const { data: subjects } = useQuery({ queryKey: ["subjects"], queryFn: schoolApi.subjects });
  const [cls, setCls] = useState({ name: "", section: "" });
  const [subj, setSubj] = useState("");
  const [assign, setAssign] = useState({ class_id: "", subject_id: "" });
  const inval = () => { qc.invalidateQueries({ queryKey: ["classes"] }); qc.invalidateQueries({ queryKey: ["subjects"] }); qc.invalidateQueries({ queryKey: ["wizard"] }); };
  const addClass = useMutation({ mutationFn: () => schoolApi.createClass({ academic_year_id: active!.id, name: cls.name, section: cls.section || null }), onSuccess: () => { inval(); setCls({ name: "", section: "" }); }, onError: (e) => showApiError(e, "Could not add class") });
  const addSubj = useMutation({ mutationFn: () => schoolApi.createSubject(subj), onSuccess: () => { inval(); setSubj(""); }, onError: (e) => showApiError(e, "Could not add subject") });
  const link = useMutation({ mutationFn: () => schoolApi.addClassSubject({ ...assign, periods_per_week: 5 }), onSuccess: () => { inval(); toast.success("Assigned"); }, onError: (e) => showApiError(e, "Could not assign") });
  if (!active) return <p className="text-sm text-muted-foreground">Create an academic year first.</p>;
  return (
    <div className="space-y-4">
      <div>
        <p className="mb-1 text-xs font-semibold text-muted-foreground">Classes</p>
        <div className="mb-2 flex flex-wrap gap-1">{classes?.map((c: SchoolClass) => <Badge key={c.id} tone="neutral">{c.name}{c.section ? `-${c.section}` : ""}</Badge>)}</div>
        <div className="flex gap-2"><Input placeholder="6" value={cls.name} onChange={(e) => setCls({ ...cls, name: e.target.value })} /><Input placeholder="A" value={cls.section} onChange={(e) => setCls({ ...cls, section: e.target.value })} /><Button onClick={() => addClass.mutate()} disabled={!cls.name}><Plus className="h-4 w-4" /></Button></div>
      </div>
      <div>
        <p className="mb-1 text-xs font-semibold text-muted-foreground">Subjects</p>
        <div className="mb-2 flex flex-wrap gap-1">{subjects?.map((s) => <Badge key={s.id} tone="neutral">{s.name}</Badge>)}</div>
        <div className="flex gap-2"><Input placeholder="Science" value={subj} onChange={(e) => setSubj(e.target.value)} /><Button onClick={() => addSubj.mutate()} disabled={!subj}><Plus className="h-4 w-4" /></Button></div>
      </div>
      <div>
        <p className="mb-1 text-xs font-semibold text-muted-foreground">Assign a subject to a class</p>
        <div className="flex flex-wrap gap-2">
          <select className="h-9 rounded-md border border-border bg-background px-2 text-sm" value={assign.class_id} onChange={(e) => setAssign({ ...assign, class_id: e.target.value })}>
            <option value="">Class…</option>{classes?.map((c: SchoolClass) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
          </select>
          <select className="h-9 rounded-md border border-border bg-background px-2 text-sm" value={assign.subject_id} onChange={(e) => setAssign({ ...assign, subject_id: e.target.value })}>
            <option value="">Subject…</option>{subjects?.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <Button onClick={() => link.mutate()} disabled={!assign.class_id || !assign.subject_id || link.isPending}>Assign</Button>
        </div>
      </div>
    </div>
  );
}

function SyllabusStep() {
  const { data: years } = useYears();
  const active = years?.find((y) => y.is_active) ?? years?.[0];
  const { data: classes } = useQuery({ queryKey: ["classes", active?.id], queryFn: () => schoolApi.classes(active?.id), enabled: !!active });
  const [classId, setClassId] = useState("");
  const { data: css } = useQuery({ queryKey: ["class-subjects", classId], queryFn: () => schoolApi.classSubjects(classId), enabled: !!classId });
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Add chapters &amp; topics per subject. Open the full Plan editor for the rich view, or add a few here.</p>
      <select className="h-9 rounded-md border border-border bg-background px-2 text-sm" value={classId} onChange={(e) => setClassId(e.target.value)}>
        <option value="">Pick a class…</option>{classes?.map((c: SchoolClass) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
      </select>
      {css?.map((cs: ClassSubject) => <SyllabusQuickAdd key={cs.id} cs={cs} />)}
      <Link href="/plan/syllabus" className="inline-flex items-center gap-1 text-sm text-primary">Open full syllabus editor <ArrowRight className="h-3.5 w-3.5" /></Link>
    </div>
  );
}

function SyllabusQuickAdd({ cs }: { cs: ClassSubject }) {
  const qc = useQueryClient();
  const { data: units } = useQuery({ queryKey: ["syllabus", cs.id], queryFn: () => schoolApi.syllabus(cs.id) });
  const [chapter, setChapter] = useState("");
  const [topic, setTopic] = useState("");
  const addUnit = useMutation({ mutationFn: () => schoolApi.addUnit({ class_subject_id: cs.id, title: chapter }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["syllabus", cs.id] }); qc.invalidateQueries({ queryKey: ["wizard"] }); setChapter(""); }, onError: (e) => showApiError(e, "Could not add") });
  const firstUnit = units?.[0];
  const addTopic = useMutation({ mutationFn: () => schoolApi.addTopic({ unit_id: firstUnit!.id, title: topic, est_periods: 3 }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["syllabus", cs.id] }); qc.invalidateQueries({ queryKey: ["wizard"] }); setTopic(""); }, onError: (e) => showApiError(e, "Could not add") });
  return (
    <div className="rounded-lg border border-border p-3">
      <p className="mb-1 text-sm font-medium">{cs.subject_name} <span className="text-xs text-muted-foreground">· {units?.length ?? 0} chapters</span></p>
      <div className="mb-2 flex gap-2"><Input placeholder="Chapter title" value={chapter} onChange={(e) => setChapter(e.target.value)} /><Button size="sm" onClick={() => addUnit.mutate()} disabled={!chapter}>Add chapter</Button></div>
      {firstUnit ? <div className="flex gap-2"><Input placeholder="Topic (into first chapter)" value={topic} onChange={(e) => setTopic(e.target.value)} /><Button size="sm" variant="outline" onClick={() => addTopic.mutate()} disabled={!topic}>Add topic</Button></div> : null}
    </div>
  );
}

function TeachersStep() {
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Add teaching staff and share their login links, then assign subjects to teachers.</p>
      <Link href="/setup/members" className="inline-flex items-center gap-1 text-sm text-primary">Open Members to add teachers <ArrowRight className="h-3.5 w-3.5" /></Link>
    </div>
  );
}

function StudentsStep() {
  const qc = useQueryClient();
  const { data: years } = useYears();
  const active = years?.find((y) => y.is_active) ?? years?.[0];
  const { data: classes } = useQuery({ queryKey: ["classes", active?.id], queryFn: () => schoolApi.classes(active?.id), enabled: !!active });
  const [f, setF] = useState({ admission_no: "", full_name: "", class_id: "" });
  const add = useMutation({
    mutationFn: () => schoolApi.createStudent({ admission_no: f.admission_no, full_name: f.full_name, class_id: f.class_id || null }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["wizard"] }); toast.success("Student added"); setF({ admission_no: "", full_name: "", class_id: f.class_id }); },
    onError: (e) => showApiError(e, "Could not add student"),
  });
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Import the roster from xlsx/CSV, or add a few students to get going.</p>
      <div className="grid gap-2 sm:grid-cols-3">
        <Input placeholder="Adm. no" value={f.admission_no} onChange={(e) => setF({ ...f, admission_no: e.target.value })} />
        <Input placeholder="Full name" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} />
        <select className="h-9 rounded-md border border-border bg-background px-2 text-sm" value={f.class_id} onChange={(e) => setF({ ...f, class_id: e.target.value })}>
          <option value="">Class…</option>{classes?.map((c: SchoolClass) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
        </select>
      </div>
      <div className="flex items-center gap-3">
        <Button onClick={() => add.mutate()} disabled={!f.admission_no || !f.full_name || add.isPending}><Plus className="h-4 w-4" /> Add student</Button>
        <Link href="/students" className="text-sm text-primary">Import roster (.xlsx)</Link>
      </div>
    </div>
  );
}

function TimetableStep() {
  const { data: years } = useYears();
  const active = years?.find((y) => y.is_active) ?? years?.[0];
  const { data: classes } = useQuery({ queryKey: ["classes", active?.id], queryFn: () => schoolApi.classes(active?.id), enabled: !!active });
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Import a photo/xlsx of your timetable, or let TrackBit draft one — then finish by drag in the Plan → Timetable editor.</p>
      <div className="flex flex-wrap gap-1">{classes?.map((c: SchoolClass) => <Badge key={c.id} tone="neutral">{c.name}{c.section ? `-${c.section}` : ""}</Badge>)}</div>
      <Link href="/plan/timetable" className="inline-flex items-center gap-1 text-sm text-primary">Open the Timetable editor <ArrowRight className="h-3.5 w-3.5" /></Link>
    </div>
  );
}

function GenerateStep({ onComplete }: { onComplete: () => void }) {
  const qc = useQueryClient();
  const { data: years } = useYears();
  const active = years?.find((y) => y.is_active) ?? years?.[0];
  const { data: classes } = useQuery({ queryKey: ["classes", active?.id], queryFn: () => schoolApi.classes(active?.id), enabled: !!active });
  const [log, setLog] = useState<string[]>([]);
  const run = useMutation({
    mutationFn: async () => {
      const lines: string[] = [];
      for (const c of classes ?? []) {
        const css = await schoolApi.classSubjects(c.id);
        for (const cs of css) {
          try {
            const g = await schoolApi.generatePlan(cs.id);
            if (!g.fits) { lines.push(`⚠ ${c.name} ${cs.subject_name}: ${g.violations.map((v) => v.message).join("; ")}`); continue; }
            await schoolApi.approvePlan(cs.id);
            lines.push(`✓ ${c.name} ${cs.subject_name}: plan locked (${g.plan.entries.length} topics)`);
          } catch {
            lines.push(`– ${c.name} ${cs.subject_name}: skipped (add syllabus topics)`);
          }
        }
      }
      return lines;
    },
    onSuccess: (lines) => { setLog(lines); qc.invalidateQueries({ queryKey: ["wizard"] }); },
    onError: (e) => showApiError(e, "Generation failed"),
  });
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted-foreground">Generate a year plan for every subject with a syllabus, validate it, and lock the baseline. Over-capacity subjects are flagged for you to trim.</p>
      <Button onClick={() => run.mutate()} disabled={run.isPending}><Sparkles className="h-4 w-4" /> {run.isPending ? "Generating…" : "Generate & lock plans"}</Button>
      {log.length > 0 ? (
        <div className="space-y-1 rounded-lg border border-border bg-muted/30 p-3 text-sm">
          {log.map((l, i) => <p key={i}>{l}</p>)}
        </div>
      ) : null}
      <Button variant="outline" onClick={onComplete}><Check className="h-4 w-4" /> Finish setup</Button>
    </div>
  );
}

function WizardInner() {
  const qc = useQueryClient();
  const { data: state } = useQuery({ queryKey: ["wizard"], queryFn: schoolApi.wizardState });
  const [localStep, setLocalStep] = useState<number | null>(null);
  const step = localStep ?? state?.current_step ?? 1;

  const advance = useMutation({
    mutationFn: (to: number) => schoolApi.wizardAdvance({ to_step: to }),
    onSuccess: (s: WizardState) => { qc.setQueryData(["wizard"], s); setLocalStep(s.current_step); },
  });
  const complete = useMutation({
    mutationFn: () => schoolApi.wizardComplete(),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["wizard"] }); toast.success("Setup complete 🎉"); },
  });

  const p = state?.progress;
  const go = (to: number) => { if (to >= 1 && to <= 9) advance.mutate(to); };

  if (state?.status === "done") {
    return (
      <div className="mx-auto max-w-md py-10 text-center">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-[#e7efe9]"><PartyPopper className="h-8 w-8 text-[#234a37]" /></div>
        <h1 className="mt-5 text-2xl font-semibold">Your school is set up</h1>
        <p className="mt-2 text-sm text-muted-foreground">Plans are locked. Teachers see their day on My Day; you get the 8 AM report on the Dashboard.</p>
        <Button className="mt-6" onClick={() => schoolApi.wizardReset().then(() => qc.invalidateQueries({ queryKey: ["wizard"] }))} variant="outline">Re-open wizard</Button>
      </div>
    );
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
      {/* stepper */}
      <ol className="space-y-1">
        {STEPS.map((label, i) => {
          const n = i + 1;
          const isDone = p ? done(p, n) : false;
          return (
            <li key={n}>
              <button onClick={() => go(n)} className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${n === step ? "bg-muted font-medium" : "hover:bg-muted/50"}`}>
                <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full text-[10px] ${isDone ? "bg-[#234a37] text-white" : n === step ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>{isDone ? <Check className="h-3 w-3" /> : n}</span>
                <span className="truncate">{label}</span>
              </button>
            </li>
          );
        })}
      </ol>

      {/* active panel */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex items-center gap-2">
          <Wand2 className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-base font-semibold">{step}. {STEPS[step - 1]}</h2>
          {p && done(p, step) ? <Badge tone="success">done</Badge> : null}
        </div>

        {step === 1 ? <YearStep /> : null}
        {step === 2 ? <div className="space-y-3"><p className="text-sm text-muted-foreground">Add exam blocks and holidays in Academics → Calendar. This step is optional — skip if you’ll add them later.</p><Link href="/setup" className="inline-flex items-center gap-1 text-sm text-primary">Open Academics <ArrowRight className="h-3.5 w-3.5" /></Link></div> : null}
        {step === 3 ? <TimingsStep /> : null}
        {step === 4 ? <ClassesStep /> : null}
        {step === 5 ? <SyllabusStep /> : null}
        {step === 6 ? <TeachersStep /> : null}
        {step === 7 ? <StudentsStep /> : null}
        {step === 8 ? <TimetableStep /> : null}
        {step === 9 ? <GenerateStep onComplete={() => complete.mutate()} /> : null}

        <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
          <Button variant="ghost" onClick={() => go(step - 1)} disabled={step === 1}><ArrowLeft className="h-4 w-4" /> Back</Button>
          {step < 9 ? <Button onClick={() => go(step + 1)}>Next <ArrowRight className="h-4 w-4" /></Button> : null}
        </div>
      </div>
    </div>
  );
}

export default function WizardPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <div>
        <div className="mb-6"><PageHeader title="Setup wizard" subtitle="Compile your year — from a blank org to a locked plan, one step at a time" /></div>
        <WizardInner />
      </div>
    </AuthGuard>
  );
}
