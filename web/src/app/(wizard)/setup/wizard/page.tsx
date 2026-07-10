"use client";

/**
 * Setup wizard (V2-P5 + V2-P7, SPRD2 §5.1).
 *
 * Ten steps in dependency order, each writing through to the real tables the moment
 * it's confirmed. Progress is read back from those tables, never from local state —
 * so refreshing, logging out, or editing something outside the wizard can't make
 * the stepper lie.
 *
 * Nothing blocks on AI. Every import step has a manual path beside it, because a
 * failed parse on a Monday morning must not brick a school's onboarding.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  FileSpreadsheet,
  GraduationCap,
  Loader2,
  PartyPopper,
  Plus,
  Sparkles,
  Trash2,
  Users,
  X,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ExamPortions } from "@/components/wizard/exam-portions";
import { Dropzone, GapQuestions, MappingPreview } from "@/components/wizard/import-panel";
import { Aside, Stat, StepFrame, StepRail } from "@/components/wizard/shell";
import { CalendarLegend, YearCalendar, type PaintKind, type PaintedRange } from "@/components/wizard/year-calendar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type {
  AnalyzeResult,
  CalendarEventType,
  SchoolClass,
  SyllabusAnalyzeResult,
  SyllabusUnitDraft,
} from "@/lib/school-types";
import { cn } from "@/lib/utils";

const PREP_STEP = 0;

function useWizard() {
  return useQuery({ queryKey: ["wizard"], queryFn: schoolApi.wizardState });
}

function useActiveYear() {
  const { data } = useQuery({ queryKey: ["academic-years"], queryFn: schoolApi.years });
  return data?.find((y) => y.is_active) ?? data?.[0] ?? null;
}

function useInvalidate() {
  const qc = useQueryClient();
  return (...keys: string[]) => {
    qc.invalidateQueries({ queryKey: ["wizard"] });
    keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  };
}

// ── 0. prep ───────────────────────────────────────────────────────────────────
const PREP_DOCS = [
  {
    icon: Users,
    title: "Teaching staff",
    columns: "Teacher Name · Email · Assignments (e.g. “6-A Mathematics; 7-B Science”)",
  },
  {
    icon: GraduationCap,
    title: "Students",
    columns: "Student Name · Admission No · Class · Section · Father/Mother phone",
  },
  {
    icon: BookOpen,
    title: "Syllabus / lesson plan",
    columns: "Chapter · Topic · Periods — or just paste the chapter list as text",
  },
];

function PrepStep({ onStart }: { onStart: () => void }) {
  const reduce = useReducedMotion();
  return (
    <div className="mx-auto flex min-h-dvh max-w-3xl flex-col justify-center px-6 py-16">
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={reduce ? { duration: 0 } : { duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        <Badge tone="primary" className="mb-4">
          <Sparkles className="h-3 w-3" /> One-time setup
        </Badge>
        <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">
          Let&apos;s build your academic year.
        </h1>
        <p className="mt-3 max-w-xl text-muted-foreground">
          We&apos;ll walk through ten steps and end with a complete, day-by-day plan for every
          class — who teaches what, when, and whether the syllabus finishes before the exams.
          It takes a while, and you only do it once.
        </p>

        <p className="mt-8 text-sm font-medium">Have these three ready. Any format — we&apos;ll read them.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          {PREP_DOCS.map((d, i) => (
            <motion.div
              key={d.title}
              initial={reduce ? false : { opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={reduce ? { duration: 0 } : { delay: 0.1 + i * 0.08, duration: 0.35 }}
              className="rounded-xl border border-border bg-card p-4"
            >
              <d.icon className="h-5 w-5 text-primary" />
              <h3 className="mt-2 text-sm font-semibold">{d.title}</h3>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{d.columns}</p>
            </motion.div>
          ))}
        </div>

        <p className="mt-6 text-xs text-muted-foreground">
          Don&apos;t have them handy? Every step can be filled in by hand instead, and you can
          leave and come back — nothing is lost.
        </p>

        <div className="mt-8 flex items-center gap-3">
          <Button size="lg" onClick={onStart}>
            Start setup <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
      </motion.div>
    </div>
  );
}

// ── 1. year ───────────────────────────────────────────────────────────────────
function YearStep() {
  const invalidate = useInvalidate();
  const year = useActiveYear();
  const [f, setF] = useState({ label: "", start_date: "", end_date: "" });

  const create = useMutation({
    mutationFn: async () => {
      const y = await schoolApi.createYear(f);
      await schoolApi.activateYear(y.id);
      return y;
    },
    onSuccess: () => {
      invalidate("academic-years");
      toast.success("Academic year created");
    },
    onError: (e) => showApiError(e, "Could not create the year"),
  });

  const start = year?.start_date ?? f.start_date;
  const end = year?.end_date ?? f.end_date;

  return (
    <StepFrame
      stepKey="year"
      title="When does the year run?"
      blurb="Everything else hangs off these two dates — the plan, the calendar, the forecast."
      aside={
        <Aside title="Your year">
          <YearCalendar startDate={start} endDate={end} />
        </Aside>
      }
    >
      {year ? (
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Check className="h-4 w-4 text-primary" /> {year.label}
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {year.start_date} → {year.end_date}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <Label htmlFor="label">Name it</Label>
            <Input
              id="label"
              placeholder="2026-27"
              value={f.label}
              onChange={(e) => setF({ ...f, label: e.target.value })}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label htmlFor="start">First day</Label>
              <Input
                id="start"
                type="date"
                value={f.start_date}
                onChange={(e) => setF({ ...f, start_date: e.target.value })}
              />
            </div>
            <div>
              <Label htmlFor="end">Last day</Label>
              <Input
                id="end"
                type="date"
                value={f.end_date}
                onChange={(e) => setF({ ...f, end_date: e.target.value })}
              />
            </div>
          </div>
          <Button
            disabled={!f.label || !f.start_date || !f.end_date || create.isPending}
            onClick={() => create.mutate()}
          >
            {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            Lock the year
          </Button>
        </div>
      )}
    </StepFrame>
  );
}

// ── 2. timings ────────────────────────────────────────────────────────────────
function addMinutes(hhmm: string, mins: number): string {
  const [h, m] = hhmm.split(":").map(Number);
  const total = h * 60 + m + mins;
  return `${String(Math.floor(total / 60) % 24).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

/** Build the day from a start time, a period length and one lunch break. */
function buildPeriods(startAt: string, count: number, minutes: number, lunchAfter: number, lunchMins: number) {
  const out: { start: string; end: string; kind: string }[] = [];
  let cursor = startAt;
  for (let i = 1; i <= count; i += 1) {
    const end = addMinutes(cursor, minutes);
    out.push({ start: cursor, end, kind: "period" });
    cursor = end;
    if (i === lunchAfter && lunchMins > 0) {
      const lunchEnd = addMinutes(cursor, lunchMins);
      out.push({ start: cursor, end: lunchEnd, kind: "break" });
      cursor = lunchEnd;
    }
  }
  return out;
}

function TimingsStep() {
  const invalidate = useInvalidate();
  const year = useActiveYear();
  const [cfg, setCfg] = useState({ startAt: "09:00", count: 8, minutes: 40, lunchAfter: 4, lunchMins: 40 });

  const periods = useMemo(
    () => buildPeriods(cfg.startAt, cfg.count, cfg.minutes, cfg.lunchAfter, cfg.lunchMins),
    [cfg],
  );

  const save = useMutation({
    mutationFn: () =>
      schoolApi.setPeriodConfig({
        academic_year_id: year!.id,
        periods_per_day: cfg.count,
        period_times: periods,
      }),
    onSuccess: () => {
      invalidate("period-config");
      toast.success("School timings saved");
    },
    onError: (e) => showApiError(e, "Could not save timings"),
  });

  if (!year) return <StepFrame stepKey="timings" title="Set the year first" >{null}</StepFrame>;

  return (
    <StepFrame
      stepKey="timings"
      title="How does a school day run?"
      blurb="Periods per day bounds the timetable grid. A partial-day exam later costs periods, not the whole day."
      aside={
        <Aside title="Your day">
          <div className="space-y-1.5">
            <AnimatePresence initial={false}>
              {periods.map((p, i) => (
                <motion.div
                  key={`${p.start}-${i}`}
                  layout
                  initial={{ opacity: 0, x: 8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ type: "spring", stiffness: 400, damping: 34 }}
                  className={cn(
                    "flex items-center justify-between rounded-lg border px-3 py-1.5 text-sm",
                    p.kind === "break"
                      ? "border-dashed border-border bg-muted/50 text-muted-foreground"
                      : "border-border bg-card",
                  )}
                >
                  <span className="font-medium">
                    {p.kind === "break" ? "Lunch" : `Period ${periods.slice(0, i + 1).filter((x) => x.kind === "period").length}`}
                  </span>
                  <span className="tabular-nums text-muted-foreground">
                    {p.start} – {p.end}
                  </span>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </Aside>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="startAt">Day starts</Label>
          <Input id="startAt" type="time" value={cfg.startAt} onChange={(e) => setCfg({ ...cfg, startAt: e.target.value })} />
        </div>
        <div>
          <Label htmlFor="count">Periods per day</Label>
          <Input id="count" type="number" min={1} max={12} value={cfg.count}
            onChange={(e) => setCfg({ ...cfg, count: Math.max(1, Number(e.target.value)) })} />
        </div>
        <div>
          <Label htmlFor="minutes">Minutes per period</Label>
          <Input id="minutes" type="number" min={20} max={90} value={cfg.minutes}
            onChange={(e) => setCfg({ ...cfg, minutes: Number(e.target.value) })} />
        </div>
        <div>
          <Label htmlFor="lunchAfter">Lunch after period</Label>
          <Input id="lunchAfter" type="number" min={0} max={cfg.count} value={cfg.lunchAfter}
            onChange={(e) => setCfg({ ...cfg, lunchAfter: Number(e.target.value) })} />
        </div>
      </div>
      <Button onClick={() => save.mutate()} disabled={save.isPending}>
        {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        Save timings
      </Button>
    </StepFrame>
  );
}

// ── 3. classes ────────────────────────────────────────────────────────────────
function ClassesStep() {
  const invalidate = useInvalidate();
  const year = useActiveYear();
  const { data: classes } = useQuery({
    queryKey: ["classes", year?.id],
    queryFn: () => schoolApi.classes(year!.id),
    enabled: !!year,
  });
  const [f, setF] = useState({ name: "", section: "" });

  const add = useMutation({
    mutationFn: () =>
      schoolApi.createClass({ academic_year_id: year!.id, name: f.name, section: f.section || null }),
    onSuccess: () => {
      invalidate("classes");
      setF({ name: "", section: "" });
    },
    onError: (e) => showApiError(e, "Could not add the class"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteClass(id),
    onSuccess: () => invalidate("classes"),
    onError: (e) => showApiError(e, "Could not remove the class"),
  });

  return (
    <StepFrame
      stepKey="classes"
      title="Which classes do you run?"
      blurb="One row per section. Class 6 with sections A and B is two entries."
      aside={
        <Aside title={`${classes?.length ?? 0} classes`}>
          <div className="flex flex-wrap gap-2">
            <AnimatePresence initial={false}>
              {classes?.map((c) => (
                <motion.span
                  key={c.id}
                  layout
                  initial={{ opacity: 0, scale: 0.85 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.85 }}
                  className="group inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-3 py-1.5 text-sm"
                >
                  {c.name}
                  {c.section ? `-${c.section}` : ""}
                  <button
                    type="button"
                    aria-label={`Remove ${c.name}`}
                    onClick={() => remove.mutate(c.id)}
                    className="text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </motion.span>
              ))}
            </AnimatePresence>
            {!classes?.length ? (
              <p className="text-sm text-muted-foreground">Nothing yet.</p>
            ) : null}
          </div>
        </Aside>
      }
    >
      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (f.name) add.mutate();
        }}
      >
        <div className="flex-1">
          <Label htmlFor="cname">Class</Label>
          <Input id="cname" placeholder="6" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        </div>
        <div className="w-24">
          <Label htmlFor="csec">Section</Label>
          <Input id="csec" placeholder="A" value={f.section} onChange={(e) => setF({ ...f, section: e.target.value })} />
        </div>
        <Button type="submit" size="icon" disabled={!f.name || add.isPending} aria-label="Add class">
          <Plus className="h-4 w-4" />
        </Button>
      </form>
      <p className="text-xs text-muted-foreground">Press enter to add another.</p>
    </StepFrame>
  );
}

// ── 4. subjects ───────────────────────────────────────────────────────────────
const COMMON_SUBJECTS = ["Mathematics", "Science", "English", "Hindi", "Social Studies", "Telugu", "Computer Science"];

function SubjectsStep() {
  const invalidate = useInvalidate();
  const { data: subjects } = useQuery({ queryKey: ["subjects"], queryFn: schoolApi.subjects });
  const [name, setName] = useState("");

  const add = useMutation({
    mutationFn: (n: string) => schoolApi.createSubject(n),
    onSuccess: () => {
      invalidate("subjects");
      setName("");
    },
    onError: (e) => showApiError(e, "Could not add the subject"),
  });

  const have = new Set((subjects ?? []).map((s) => s.name.toLowerCase()));

  return (
    <StepFrame
      stepKey="subjects"
      title="What do you teach?"
      blurb="Just the names for now. You'll say who teaches which class next."
      aside={
        <Aside title={`${subjects?.length ?? 0} subjects`}>
          <div className="flex flex-wrap gap-2">
            {subjects?.map((s) => (
              <motion.span
                key={s.id}
                layout
                initial={{ opacity: 0, scale: 0.85 }}
                animate={{ opacity: 1, scale: 1 }}
                className="rounded-lg border border-border bg-card px-3 py-1.5 text-sm"
              >
                {s.name}
              </motion.span>
            ))}
            {!subjects?.length ? <p className="text-sm text-muted-foreground">Nothing yet.</p> : null}
          </div>
        </Aside>
      }
    >
      <form
        className="flex items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (name) add.mutate(name);
        }}
      >
        <div className="flex-1">
          <Label htmlFor="sname">Subject</Label>
          <Input id="sname" placeholder="Mathematics" value={name} onChange={(e) => setName(e.target.value)} />
        </div>
        <Button type="submit" size="icon" disabled={!name || add.isPending} aria-label="Add subject">
          <Plus className="h-4 w-4" />
        </Button>
      </form>

      <div>
        <p className="mb-2 text-xs text-muted-foreground">Or tap the usual ones:</p>
        <div className="flex flex-wrap gap-1.5">
          {COMMON_SUBJECTS.filter((s) => !have.has(s.toLowerCase())).map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => add.mutate(s)}
              className="rounded-full border border-dashed border-border px-2.5 py-1 text-xs hover:bg-muted"
            >
              + {s}
            </button>
          ))}
        </div>
      </div>
    </StepFrame>
  );
}

// ── 5. staff + assignments ────────────────────────────────────────────────────
const STAFF_LABELS = {
  full_name: "Name",
  username: "Username",
  email: "Email",
  phone: "Phone",
  assignments: "Classes & subjects",
};

function StaffStep() {
  const invalidate = useInvalidate();
  const year = useActiveYear();
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);
  const { data: members } = useQuery({ queryKey: ["members"], queryFn: appApi.members });
  const teachers = (members?.members ?? []).filter((m) => m.role === "teacher");

  const analyze = useMutation({
    mutationFn: (f: File) => schoolApi.staffImportAnalyze(f),
    onSuccess: setAnalysis,
    onError: (e) => showApiError(e, "Could not read that file"),
  });

  const commit = useMutation({
    mutationFn: () =>
      schoolApi.staffImportCommit({
        mapping: analysis!.mapping,
        rows: analysis!.rows,
        academic_year_id: year?.id ?? null,
      }),
    onSuccess: (r) => {
      invalidate("members", "class-subjects");
      setAnalysis(null);
      toast.success(`${r.created_count} teachers added · ${r.assigned} assignments made`);
      if (r.unresolved.length) {
        toast.warning(
          `Couldn't place ${r.unresolved.length} assignment hint(s) — add those by hand.`,
        );
      }
    },
    onError: (e) => showApiError(e, "Could not import staff"),
  });

  return (
    <StepFrame
      stepKey="staff"
      title="Who teaches here?"
      blurb="Drop your staff sheet. If it has a column like “6-A Mathematics”, we'll wire up the assignments too."
      aside={
        <Aside title={`${teachers.length} teachers`}>
          <div className="space-y-1.5">
            {teachers.map((t) => (
              <motion.div
                key={t.user_id}
                layout
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-sm"
              >
                <span className="font-medium">{t.name}</span>
                <span className="text-xs text-muted-foreground">{t.username ?? t.email}</span>
              </motion.div>
            ))}
            {!teachers.length ? (
              <p className="text-sm text-muted-foreground">No teachers yet.</p>
            ) : null}
          </div>
          {commit.data?.created.length ? (
            <div className="mt-4 rounded-xl border border-border bg-warning-soft/40 p-3">
              <p className="text-xs font-semibold text-warning">
                Copy these passwords now — they aren&apos;t shown again.
              </p>
              <ul className="mt-1.5 space-y-0.5 font-mono text-xs">
                {commit.data.created.map((c) => (
                  <li key={c.user_id}>
                    {c.username} · {c.password}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </Aside>
      }
    >
      {!analysis ? (
        <>
          <Dropzone
            busy={analyze.isPending}
            onFile={(f) => analyze.mutate(f)}
            hint="xlsx or csv · Name, Email, Assignments"
          />
          <p className="text-xs text-muted-foreground">
            No sheet? Add staff by hand later from Setup → Members. This step can be skipped.
          </p>
        </>
      ) : (
        <div className="space-y-3">
          <MappingPreview analysis={analysis} labels={STAFF_LABELS} />
          <GapQuestions
            analysis={analysis}
            onAnswer={(field, column) => {
              setAnalysis((a) => {
                if (!a) return a;
                const mapping = { ...a.mapping };
                if (column) mapping[field] = column;
                return {
                  ...a,
                  mapping,
                  missing_required: a.missing_required.filter((f) => f !== field),
                  questions: a.questions.filter((q) => q.field !== field),
                };
              });
            }}
          />
          <div className="flex gap-2">
            <Button onClick={() => commit.mutate()} disabled={commit.isPending}>
              {commit.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Import {analysis.row_count} teachers
            </Button>
            <Button variant="ghost" onClick={() => setAnalysis(null)}>
              Start over
            </Button>
          </div>
        </div>
      )}
    </StepFrame>
  );
}

// ── 6. syllabus ───────────────────────────────────────────────────────────────
function SyllabusStep() {
  const invalidate = useInvalidate();
  const year = useActiveYear();
  const { data: classes } = useQuery({
    queryKey: ["classes", year?.id],
    queryFn: () => schoolApi.classes(year!.id),
    enabled: !!year,
  });
  // Selections are DERIVED from what loaded, with an explicit pick overriding.
  // Syncing them in an effect would cascade a render on every refetch.
  const [pickedClass, setClassId] = useState<string>("");
  const classId = pickedClass || classes?.[0]?.id || "";
  const { data: css } = useQuery({
    queryKey: ["class-subjects", classId],
    queryFn: () => schoolApi.classSubjects(classId),
    enabled: !!classId,
  });
  const [pickedCs, setCsId] = useState<string>("");
  // A pick from a previous class won't exist in this class's list; fall back.
  const csId = css?.some((c) => c.id === pickedCs) ? pickedCs : (css?.[0]?.id ?? "");
  const [draft, setDraft] = useState<SyllabusAnalyzeResult | null>(null);
  const [text, setText] = useState("");

  const analyzeFile = useMutation({
    mutationFn: (f: File) => schoolApi.syllabusImportAnalyze(f),
    onSuccess: setDraft,
    onError: (e) => showApiError(e, "Could not read that file"),
  });
  const analyzeText = useMutation({
    mutationFn: () => schoolApi.syllabusImportText(text),
    onSuccess: setDraft,
    onError: (e) => showApiError(e, "Could not read that text"),
  });
  const commit = useMutation({
    mutationFn: () =>
      schoolApi.syllabusImportCommit({ class_subject_id: csId, units: draft!.units, replace: true }),
    onSuccess: (r) => {
      invalidate("syllabus");
      setDraft(null);
      setText("");
      toast.success(`${r.units_created} chapters · ${r.topics_created} topics`);
    },
    onError: (e) => showApiError(e, "Could not save the syllabus"),
  });

  const setEst = (ui: number, ti: number, v: number | null) =>
    setDraft((d) => {
      if (!d) return d;
      const units: SyllabusUnitDraft[] = d.units.map((u, i) =>
        i !== ui ? u : { ...u, topics: u.topics.map((t, j) => (j !== ti ? t : { ...t, est_periods: v })) },
      );
      return { ...d, units };
    });

  // Unsized topics contribute nothing to the total and are counted separately —
  // "80 periods" over a syllabus with 12 unsized chapters is not a real number.
  const totalPeriods = draft?.units.reduce((a, u) => a + u.topics.reduce((b, t) => b + (t.est_periods ?? 0), 0), 0) ?? 0;
  const unsizedCount = draft?.units.reduce((a, u) => a + u.topics.filter((t) => t.est_periods === null).length, 0) ?? 0;

  return (
    <StepFrame
      stepKey="syllabus"
      title="What's the syllabus?"
      blurb="Per class-subject. Import a sheet, paste the chapter list, or type it — whichever is quickest."
      aside={
        <Aside title={draft ? `Draft · ${totalPeriods} periods${unsizedCount ? ` · ${unsizedCount} unsized` : ""}` : "Nothing loaded"}>
          {draft ? (
            <div className="max-h-[70vh] space-y-2 overflow-auto pr-1">
              {draft.units.map((u, ui) => (
                <motion.div
                  key={`${u.title}-${ui}`}
                  layout
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-xl border border-border bg-card p-3"
                >
                  <h3 className="text-sm font-semibold">{u.title}</h3>
                  <ul className="mt-1.5 space-y-1">
                    {u.topics.map((t, ti) => (
                      <li key={ti} className="flex items-center justify-between gap-2 text-sm">
                        <span className="min-w-0 truncate text-muted-foreground">{t.title}</span>
                        <input
                          type="number"
                          min={1}
                          placeholder="—"
                          aria-label={`Periods for ${t.title}`}
                          // "" keeps the input controlled while the topic is unsized;
                          // clearing it sets est_periods back to null rather than 1.
                          value={t.est_periods ?? ""}
                          onChange={(e) => setEst(ui, ti, e.target.value === "" ? null : Math.max(1, Number(e.target.value)))}
                          className={`h-7 w-14 rounded-md border bg-background px-1.5 text-center text-xs tabular-nums ${t.est_periods === null ? "border-warning" : "border-input"}`}
                        />
                      </li>
                    ))}
                  </ul>
                </motion.div>
              ))}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              Your chapters will appear here for review before anything is saved.
            </div>
          )}
        </Aside>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="cls">Class</Label>
          <select
            id="cls"
            value={classId}
            onChange={(e) => setClassId(e.target.value)}
            className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            {classes?.map((c: SchoolClass) => (
              <option key={c.id} value={c.id}>
                {c.name}
                {c.section ? `-${c.section}` : ""}
              </option>
            ))}
          </select>
        </div>
        <div>
          <Label htmlFor="cs">Subject</Label>
          <select
            id="cs"
            value={csId}
            onChange={(e) => setCsId(e.target.value)}
            className="h-11 w-full rounded-md border border-input bg-background px-3 text-sm"
          >
            {css?.map((cs) => (
              <option key={cs.id} value={cs.id}>
                {cs.subject_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {!css?.length ? (
        <p className="rounded-lg border border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground">
          This class has no subjects assigned yet — go back to Teachers &amp; assignments.
        </p>
      ) : null}

      {!draft ? (
        <>
          <Dropzone
            busy={analyzeFile.isPending}
            onFile={(f) => analyzeFile.mutate(f)}
            accept=".xlsx,.xls,.csv,.pdf,.png,.jpg,.jpeg,.webp"
            hint="Chapter · Topic · Periods — or a PDF / photo of a printed syllabus"
          />
          <div className="space-y-2">
            <Label htmlFor="paste">Or paste it</Label>
            <textarea
              id="paste"
              rows={6}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={"Chapter 1: Food\nSources of food (3)\nComponents of food - 2 periods"}
              className="w-full rounded-md border border-input bg-background p-3 font-mono text-xs"
            />
            <Button variant="outline" disabled={!text || analyzeText.isPending} onClick={() => analyzeText.mutate()}>
              <FileSpreadsheet className="h-4 w-4" /> Read this
            </Button>
          </div>
        </>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {draft.unit_count} chapters, {draft.topic_count} topics. Check the period estimates on
            the right — the whole plan is built from them.
          </p>
          <div className="flex gap-2">
            <Button disabled={!csId || commit.isPending} onClick={() => commit.mutate()}>
              {commit.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save to this subject
            </Button>
            <Button variant="ghost" onClick={() => setDraft(null)}>
              Discard
            </Button>
          </div>
        </div>
      )}
    </StepFrame>
  );
}

// ── 7. calendar + exams ───────────────────────────────────────────────────────
const KINDS: { kind: PaintKind; label: string }[] = [
  { kind: "exam_block", label: "Exam" },
  { kind: "holiday", label: "Holiday" },
  { kind: "celebration", label: "Celebration" },
  { kind: "event", label: "Event" },
];

function CalendarStep() {
  const invalidate = useInvalidate();
  const year = useActiveYear();
  const { data: summary } = useQuery({
    queryKey: ["calendar", year?.id],
    queryFn: () => schoolApi.calendarSummary(year!.id),
    enabled: !!year,
  });
  const { data: classes } = useQuery({
    queryKey: ["classes", year?.id],
    queryFn: () => schoolApi.classes(year!.id),
    enabled: !!year,
  });
  const [kind, setKind] = useState<PaintKind>("exam_block");
  const [title, setTitle] = useState("Term 1 Exam");

  const create = useMutation({
    mutationFn: (r: { start: string; end: string }) =>
      schoolApi.createEvents([
        {
          academic_year_id: year!.id,
          type: kind as CalendarEventType,
          title: title || KINDS.find((k) => k.kind === kind)!.label,
          start_date: r.start,
          end_date: r.end,
        },
      ]),
    onSuccess: () => {
      invalidate("calendar");
      toast.success("Added to the calendar");
    },
    onError: (e) => showApiError(e, "Could not add that"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteEvent(id),
    onSuccess: () => invalidate("calendar"),
  });

  const ranges: PaintedRange[] = (summary?.events ?? []).map((e) => ({
    start: e.start_date,
    end: e.end_date,
    kind: e.type as PaintKind,
    title: e.title,
  }));

  if (!year) return <StepFrame stepKey="calendar" title="Set the year first">{null}</StepFrame>;

  return (
    <StepFrame
      stepKey="calendar"
      title="Mark the exams, holidays and events."
      blurb="Pick a kind, name it, then drag across the days — like picking seats. Teaching days update as you go."
      aside={
        <Aside>
          <div className="mb-3 flex items-center justify-between">
            <CalendarLegend />
            <Badge tone="primary">{summary?.teaching_days ?? 0} teaching days</Badge>
          </div>
          <YearCalendar
            startDate={year.start_date}
            endDate={year.end_date}
            ranges={ranges}
            paintable
            workingWeekdays={summary?.working_weekdays}
            onPaint={(start, end) => create.mutate({ start, end })}
          />
        </Aside>
      }
    >
      <div className="space-y-3">
        <div>
          <Label>What are you marking?</Label>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {KINDS.map((k) => (
              <button
                key={k.kind}
                type="button"
                onClick={() => {
                  setKind(k.kind);
                  setTitle(k.label);
                }}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-xs transition-colors",
                  kind === k.kind
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card hover:bg-muted",
                )}
              >
                {k.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <Label htmlFor="etitle">Call it</Label>
          <Input id="etitle" value={title} onChange={(e) => setTitle(e.target.value)} />
        </div>
        <p className="text-xs text-muted-foreground">
          Now drag across the calendar.
        </p>

        <ExamPortions
          exams={(summary?.events ?? []).filter((e) => e.type === "exam_block")}
          classes={classes ?? []}
        />

        <div className="max-h-64 space-y-1.5 overflow-auto pr-1">
          <AnimatePresence initial={false}>
            {summary?.events.map((e) => (
              <motion.div
                key={e.id}
                layout
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 6 }}
                className="group flex items-center justify-between rounded-lg border border-border bg-card px-3 py-1.5 text-sm"
              >
                <span className="min-w-0 truncate">
                  <span className="font-medium">{e.title}</span>{" "}
                  <span className="text-xs text-muted-foreground">
                    {e.start_date === e.end_date ? e.start_date : `${e.start_date} → ${e.end_date}`}
                  </span>
                </span>
                <button
                  type="button"
                  aria-label={`Remove ${e.title}`}
                  onClick={() => remove.mutate(e.id)}
                  className="text-muted-foreground opacity-0 group-hover:opacity-100"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </StepFrame>
  );
}

// ── 8. students ───────────────────────────────────────────────────────────────
function StudentsStep() {
  const invalidate = useInvalidate();
  const year = useActiveYear();
  const { data: students } = useQuery({ queryKey: ["students"], queryFn: () => schoolApi.students() });
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);

  const analyze = useMutation({
    mutationFn: (f: File) => schoolApi.importRosterAnalyze(f),
    onSuccess: (r) => setAnalysis(r as unknown as AnalyzeResult),
    onError: (e) => showApiError(e, "Could not read that file"),
  });
  const commit = useMutation({
    mutationFn: () =>
      schoolApi.importRosterCommit({
        mapping: analysis!.mapping,
        rows: analysis!.rows,
        academic_year_id: year?.id ?? null,
      }),
    onSuccess: (r) => {
      invalidate("students");
      setAnalysis(null);
      toast.success(`${r.created} students added`);
    },
    onError: (e) => showApiError(e, "Could not import students"),
  });

  return (
    <StepFrame
      stepKey="students"
      title="Who's on the roll?"
      blurb="Drop your roster. Class and section are matched against the classes you created."
      aside={
        <Aside title={`${students?.length ?? 0} students`}>
          <div className="grid grid-cols-2 gap-2">
            <Stat label="On the roll" value={students?.length ?? 0} />
            <Stat label="In the file" value={analysis?.row_count ?? "—"} />
          </div>
        </Aside>
      }
    >
      {!analysis ? (
        <Dropzone busy={analyze.isPending} onFile={(f) => analyze.mutate(f)} hint="xlsx · Name, Admission No, Class, Section" />
      ) : (
        <div className="space-y-3">
          <MappingPreview
            analysis={analysis}
            labels={{
              full_name: "Name",
              admission_no: "Admission no.",
              class_name: "Class",
              section: "Section",
              father_phone: "Father's phone",
              mother_phone: "Mother's phone",
            }}
          />
          <div className="flex gap-2">
            <Button onClick={() => commit.mutate()} disabled={commit.isPending}>
              {commit.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Import {analysis.row_count} students
            </Button>
            <Button variant="ghost" onClick={() => setAnalysis(null)}>
              Start over
            </Button>
          </div>
        </div>
      )}
    </StepFrame>
  );
}

// ── 9. timetable ──────────────────────────────────────────────────────────────
function TimetableStep() {
  const year = useActiveYear();
  const { data: wizard } = useWizard();
  const router = useRouter();
  return (
    <StepFrame
      stepKey="timetable"
      title="Lay out the week."
      blurb="The grid decides which teacher is in which room at which period — and the plan reads it."
      aside={
        <Aside title="Where you are">
          <div className="grid grid-cols-2 gap-2">
            <Stat label="Slots filled" value={wizard?.progress.timetable_slots ?? 0} />
            <Stat label="Periods per day" value={year ? "set" : "—"} />
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            We don&apos;t auto-solve timetables — a wrong one breaks the whole school&apos;s day.
            Import yours or draft it, then fix clashes by hand; the clash checker is deterministic.
          </p>
        </Aside>
      }
    >
      <p className="text-sm text-muted-foreground">
        The timetable editor is a full-width grid, so it lives on its own page. Fill it in there,
        then come back and generate the plan.
      </p>
      <Button variant="outline" onClick={() => router.push("/plan/timetable")}>
        Open the timetable editor <ArrowRight className="h-4 w-4" />
      </Button>
    </StepFrame>
  );
}

// ── 10. generate ──────────────────────────────────────────────────────────────
type GenRow = { csId: string; label: string; fits: boolean; violations: { code: string; message: string }[] };

function GenerateStep({ onDone }: { onDone: () => void }) {
  const invalidate = useInvalidate();
  const year = useActiveYear();
  const { data: classes } = useQuery({
    queryKey: ["classes", year?.id],
    queryFn: () => schoolApi.classes(year!.id),
    enabled: !!year,
  });
  const [rows, setRows] = useState<GenRow[]>([]);

  const run = useMutation({
    mutationFn: async () => {
      const out: GenRow[] = [];
      for (const c of classes ?? []) {
        const css = await schoolApi.classSubjects(c.id);
        for (const cs of css) {
          const label = `${c.name}${c.section ? `-${c.section}` : ""} ${cs.subject_name}`;
          try {
            const g = await schoolApi.generatePlan(cs.id);
            out.push({ csId: cs.id, label, fits: g.fits, violations: g.violations });
          } catch {
            out.push({ csId: cs.id, label, fits: false, violations: [{ code: "error", message: "Could not generate — check the syllabus." }] });
          }
        }
      }
      return out;
    },
    onSuccess: (out) => {
      setRows(out);
      invalidate("plan");
    },
    onError: (e) => showApiError(e, "Generation failed"),
  });

  // Lock only what actually fits. A class-subject whose syllabus still has unsized
  // chapters cannot be approved (the server refuses), and a school that plans term
  // by term will always have some — so the wizard finishes with the rest locked
  // rather than failing outright on the first one.
  const approve = useMutation({
    mutationFn: async () => {
      const lockable = rows.filter((r) => r.fits);
      for (const r of lockable) await schoolApi.approvePlan(r.csId);
      return { locked: lockable.length, skipped: rows.length - lockable.length };
    },
    onSuccess: async ({ locked, skipped }) => {
      await schoolApi.wizardComplete();
      invalidate("plan");
      toast.success(skipped
        ? `${locked} plan(s) locked · ${skipped} left open — size their chapters, then approve from Plan → Week plan`
        : "Plans approved and locked");
      onDone();
    },
    onError: (e) => showApiError(e, "Could not approve the plans"),
  });

  const clean = rows.length > 0 && rows.every((r) => r.fits && !r.violations.length);
  const problems = rows.filter((r) => r.violations.length);
  const lockableCount = rows.filter((r) => r.fits).length;

  return (
    <StepFrame
      stepKey="generate"
      title="Build the plan."
      blurb="We place every chapter into a week, then check it against capacity, ordering, teacher load and your exam dates."
      aside={
        <Aside title="Results">
          {!rows.length ? (
            <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
              Nothing generated yet.
            </div>
          ) : (
            <div className="max-h-[70vh] space-y-1.5 overflow-auto pr-1">
              {rows.map((r) => (
                <motion.div
                  key={r.label}
                  layout
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="rounded-xl border border-border bg-card px-3 py-2"
                >
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium">{r.label}</span>
                    <Badge tone={r.violations.length ? (r.fits ? "warning" : "danger") : "success"}>
                      {r.violations.length ? `${r.violations.length} to check` : "clean"}
                    </Badge>
                  </div>
                  {r.violations.map((v, i) => (
                    <p key={i} className="mt-1 text-xs text-muted-foreground">
                      {v.message}
                    </p>
                  ))}
                </motion.div>
              ))}
            </div>
          )}
        </Aside>
      }
    >
      <Button onClick={() => run.mutate()} disabled={run.isPending}>
        {run.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
        Generate every plan
      </Button>

      {rows.length ? (
        <div className="space-y-3">
          {problems.length ? (
            <p className="rounded-lg border border-border bg-warning-soft/50 px-3 py-2 text-sm text-warning">
              {problems.length} subject{problems.length === 1 ? "" : "s"} need a look. Nothing was
              squeezed to make it fit — trim topics, add periods, or move an exam.
            </p>
          ) : null}
          {clean ? (
            <p className="rounded-lg border border-border bg-accent px-3 py-2 text-sm text-accent-foreground">
              Every subject fits, in order, before its exams.
            </p>
          ) : null}
          <Button variant={clean ? "primary" : "outline"} onClick={() => approve.mutate()} disabled={approve.isPending}>
            {approve.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            {lockableCount === 0
              ? "Finish without locking"
              : `Approve & lock ${lockableCount} plan${lockableCount === 1 ? "" : "s"}`}
          </Button>
          <p className="text-xs text-muted-foreground">
            Locking makes the plan the baseline. Actual progress is measured against it from your
            teachers&apos; daily logs — the plan itself never silently changes.
            {rows.length - lockableCount > 0 ? (
              <> Subjects with chapters that have no period estimate stay open — plan them from
              Plan → Week plan when their term begins.</>
            ) : null}
          </p>
        </div>
      ) : null}
    </StepFrame>
  );
}

// ── done ──────────────────────────────────────────────────────────────────────
function DoneScreen() {
  const router = useRouter();
  const reduce = useReducedMotion();
  return (
    <div className="mx-auto flex min-h-dvh max-w-xl flex-col items-center justify-center px-6 text-center">
      <motion.div
        initial={reduce ? false : { scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={reduce ? { duration: 0 } : { type: "spring", stiffness: 260, damping: 18 }}
      >
        <PartyPopper className="mx-auto h-12 w-12 text-primary" />
      </motion.div>
      <h1 className="mt-5 text-3xl font-semibold tracking-tight">Your year is planned.</h1>
      <p className="mt-2 text-muted-foreground">
        Every teacher will find their periods waiting on My Day tomorrow morning. You&apos;ll get
        the school&apos;s report at 8 AM.
      </p>
      <Button className="mt-8" size="lg" onClick={() => router.push("/dashboard")}>
        Go to the dashboard <ArrowRight className="h-4 w-4" />
      </Button>
    </div>
  );
}

// ── shell ─────────────────────────────────────────────────────────────────────
function WizardBody() {
  const { data: wizard, isLoading } = useWizard();
  const [picked, setPicked] = useState<number | null>(null);
  const [finished, setFinished] = useState(false);

  // Resume where the admin left off. `current_step` is server state, so this
  // survives a logout; the prep screen only shows on a truly fresh org. Derived
  // rather than synced in an effect — `picked` simply wins once they navigate.
  const resume = wizard
    ? !wizard.progress.has_year && wizard.current_step <= 1
      ? PREP_STEP
      : wizard.current_step
    : null;
  const step = picked ?? resume;

  const advance = useMutation({ mutationFn: (to: number) => schoolApi.wizardAdvance({ to_step: to }) });

  const go = (to: number) => {
    const clamped = Math.max(PREP_STEP, Math.min(to, wizard?.total_steps ?? 10));
    setPicked(clamped);
    if (clamped >= 1) advance.mutate(clamped);
    if (typeof window !== "undefined") window.scrollTo({ top: 0, behavior: "smooth" });
  };

  if (isLoading || step === null || !wizard) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (finished) return <DoneScreen />;
  if (step === PREP_STEP) return <PrepStep onStart={() => go(1)} />;

  const panels: Record<number, React.ReactNode> = {
    1: <YearStep />,
    2: <TimingsStep />,
    3: <ClassesStep />,
    4: <SubjectsStep />,
    5: <StaffStep />,
    6: <SyllabusStep />,
    7: <CalendarStep />,
    8: <StudentsStep />,
    9: <TimetableStep />,
    10: <GenerateStep onDone={() => setFinished(true)} />,
  };

  return (
    <div className="mx-auto flex min-h-dvh max-w-7xl flex-col px-6 py-6">
      <header className="mb-8 flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Setup · step {step} of {wizard.total_steps}
          </span>
          <Button variant="ghost" size="sm" onClick={() => setFinished(true)}>
            Finish later
          </Button>
        </div>
        <StepRail steps={wizard.steps} current={step} onJump={go} />
      </header>

      <main className="flex flex-1 flex-col">{panels[step]}</main>

      <footer className="mt-10 flex items-center justify-between border-t border-border pt-4">
        <Button variant="ghost" onClick={() => go(step - 1)} disabled={step <= 1}>
          <ArrowLeft className="h-4 w-4" /> Back
        </Button>
        <Button onClick={() => go(step + 1)} disabled={step >= wizard.total_steps}>
          Next <ArrowRight className="h-4 w-4" />
        </Button>
      </footer>
    </div>
  );
}

export default function WizardPage() {
  return (
    <AuthGuard requireRole="admin">
      <WizardBody />
    </AuthGuard>
  );
}
