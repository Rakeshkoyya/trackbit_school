"use client";

/**
 * Class row, subject row (founder, SY-2).
 *
 * Plan → Syllabus used to hand an admin the whole school as one long table and
 * ask her to filter it. That is the right shape for *"which chapters are
 * late?"* and the wrong one for the thing she actually opens the page to do,
 * which is **work on one subject of one class** — the shape of the tracker
 * spreadsheet the school already keeps, one sheet per class, subjects down it.
 *
 * So the navigation is two rows of chips, not two dropdowns:
 *
 *   · a chip row shows how many classes there ARE. A `<select>` hides that
 *     behind a click, and the count is the first thing that tells an admin her
 *     import worked;
 *   · the current pick stays visible without opening anything, which matters
 *     when the table below it is the whole screen;
 *   · a subject chip can carry its mentor, and a class chip its section — a
 *     dropdown option cannot carry a second line.
 *
 * The rightmost control on each row ADDS. Putting "add a class" anywhere else
 * means a school whose import missed one has to leave for Setup and come back,
 * and after handover Setup is frozen to her entirely (`D-1`) — whereas the two
 * writes here are the ordinary ones a live school makes.
 *
 * **A teacher gets exactly the same component.** The server decides what is in
 * `classes`/`subjects` — `?mine=true` on classes and her own `class_subjects`
 * — so her rows are short and her Add buttons are absent, and there is no
 * second, thinner picker for her to keep in step with this one.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Modal } from "@/components/ui/modal";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { ClassSubject, SchoolClass } from "@/lib/school-types";
import { cn } from "@/lib/utils";

/** School order, not string order — `10` after `9`, `7-A` before `7-B`.
 *  The server sorts by `SchoolClass.name`, which is TEXT, so a school with a
 *  class 11 and a class 3 reads "11, 12, 3, 5, 7". Exported because every
 *  screen with a class picker needs the same order. */
export function sortClasses(classes: SchoolClass[]): SchoolClass[] {
  return [...classes].sort((a, b) =>
    a.name.localeCompare(b.name, undefined, { numeric: true })
    || (a.section ?? "").localeCompare(b.section ?? ""));
}

export const classLabel = (c: SchoolClass) =>
  `${c.name}${c.section ? `-${c.section}` : ""}`;

// ── the chip rows ────────────────────────────────────────────────────────────
function Chip({ active, onClick, label, caption }: {
  active: boolean; onClick: () => void; label: string; caption?: string | null;
}) {
  return (
    <button type="button" onClick={onClick} aria-pressed={active}
      className={cn(
        "shrink-0 rounded-full border px-3 py-1.5 text-left text-sm transition-colors",
        active
          ? "border-primary bg-primary text-primary-foreground"
          : "border-border bg-card hover:border-primary/60 hover:bg-muted")}>
      <span className="font-medium">{label}</span>
      {caption ? (
        // The mentor rides on the chip. It is the column the founder's tracker
        // carries per chapter, and it is the same person for every chapter of a
        // subject — so it belongs on the subject, said once.
        <span className={cn("ml-1.5 font-mono text-[10px]",
          active ? "opacity-75" : "text-muted-foreground")}>{caption}</span>
      ) : null}
    </button>
  );
}

function Row({ label, children, action }: {
  label: string; children: React.ReactNode; action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-14 shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
        {label}
      </span>
      {/* The chips scroll inside their own row; the page never moves sideways
          however many classes a school has. */}
      <div className="flex min-w-0 flex-1 gap-1.5 overflow-x-auto pb-0.5"
        style={{ contain: "layout inline-size" }}>
        {children}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}

// ── add a class ──────────────────────────────────────────────────────────────
function AddClass({ yearId, onAdded }: {
  yearId: string | null; onAdded: (c: SchoolClass) => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [section, setSection] = useState("");

  const save = useMutation({
    mutationFn: () => schoolApi.createClass({
      academic_year_id: yearId!, name: name.trim(),
      section: section.trim() || null,
    }),
    onSuccess: (c) => {
      toast.success(`${c.name}${c.section ? `-${c.section}` : ""} added`);
      setName(""); setSection(""); setOpen(false);
      onAdded(c);
    },
    onError: (e) => showApiError(e, "Could not add the class"),
  });

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}
        disabled={!yearId}>
        <Plus className="h-4 w-4" /> Class
      </Button>
      <Modal open={open} onOpenChange={setOpen} title="Add a class"
        description="A class in this academic year. Its subjects come next.">
        <form className="space-y-4"
          onSubmit={(e) => { e.preventDefault(); if (name.trim()) save.mutate(); }}>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Class</Label>
              <Input autoFocus placeholder="6" value={name}
                onChange={(e) => setName(e.target.value)} />
            </div>
            <div>
              <Label>Section (optional)</Label>
              <Input placeholder="A" value={section}
                onChange={(e) => setSection(e.target.value)} />
            </div>
          </div>
          <Button type="submit" className="w-full"
            disabled={!name.trim() || save.isPending}>
            {save.isPending ? "Adding…" : "Add class"}
          </Button>
        </form>
      </Modal>
    </>
  );
}

// ── add a subject to THIS class, with its mentor ─────────────────────────────
function AddSubject({ classId, onAdded }: {
  classId: string; onAdded: (cs: ClassSubject) => void;
}) {
  const [open, setOpen] = useState(false);
  const [subjectId, setSubjectId] = useState("");
  const [newName, setNewName] = useState("");
  const [teacher, setTeacher] = useState("");
  const qc = useQueryClient();

  // Every subject the school has, and everyone who could teach it. Both are
  // needed the moment the dialog opens, so neither is lazy.
  const { data: subjects = [] } = useQuery({
    queryKey: ["subjects"], queryFn: schoolApi.subjects, enabled: open,
  });
  const { data: members } = useQuery({
    queryKey: ["members"], queryFn: appApi.members, enabled: open,
  });
  // The operator is a member of every school and is not staff (`core/staff.py`
  // draws the same line server-side) — offering "TrackBit Ops" as a mentor
  // would be offering us.
  const staff = (members?.members ?? []).filter(
    (mm) => mm.member_id && !(mm.email ?? "").endsWith("@trackbit.app"));

  const save = useMutation({
    mutationFn: async () => {
      // A subject the school has not named yet is created first, in the same
      // gesture: making her leave for Setup to type one word is the reason
      // subjects go unrecorded.
      const sid = subjectId
        ? subjectId
        : (await schoolApi.createSubject(newName.trim())).id;
      // No periods/week here (TT-3). It is COUNTED off the timetable now, so
      // asking for it would be asking the school to guess a number we work out
      // ourselves — and a guess typed here would be overwritten by the first
      // grid edit anyway.
      return schoolApi.addClassSubject({
        class_id: classId, subject_id: sid,
        teacher_member_id: teacher || null,
      });
    },
    onSuccess: (cs) => {
      toast.success("Subject added to this class");
      qc.invalidateQueries({ queryKey: ["subjects"] });
      setSubjectId(""); setNewName(""); setTeacher(""); setOpen(false);
      onAdded(cs);
    },
    onError: (e) => showApiError(e, "Could not add the subject"),
  });

  const ready = Boolean(subjectId || newName.trim());

  return (
    <>
      <Button size="sm" variant="outline" onClick={() => setOpen(true)}>
        <Plus className="h-4 w-4" /> Subject
      </Button>
      <Modal open={open} onOpenChange={setOpen} title="Add a subject"
        description="On this class, with the teacher who owns it.">
        <form className="space-y-4"
          onSubmit={(e) => { e.preventDefault(); if (ready) save.mutate(); }}>
          <div>
            <Label>Subject</Label>
            <select value={subjectId}
              onChange={(e) => { setSubjectId(e.target.value); setNewName(""); }}
              className="w-full rounded-md border border-border bg-card px-2.5 py-2 text-sm">
              <option value="">— a new subject —</option>
              {subjects.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            {!subjectId ? (
              <Input className="mt-2" placeholder="Name the new subject"
                value={newName} onChange={(e) => setNewName(e.target.value)} />
            ) : null}
          </div>
          <div>
            <Label>Mentor</Label>
            <select value={teacher} onChange={(e) => setTeacher(e.target.value)}
              className="w-full rounded-md border border-border bg-card px-2.5 py-2 text-sm">
              <option value="">Not assigned yet</option>
              {staff.map((mm) => (
                <option key={mm.member_id!} value={mm.member_id!}>
                  {mm.name}{mm.role === "admin" ? " · admin" : ""}
                </option>
              ))}
            </select>
            <p className="mt-1 text-[11px] text-muted-foreground">
              The teacher this subject belongs to. She is the one who may edit
              its syllabus, and the one every chapter of it is filed under.
            </p>
          </div>
          <p className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-[11px] leading-snug text-muted-foreground">
            <span className="font-medium text-foreground">Periods a week are
            counted from the timetable.</span> Put this subject on the grid and
            its weekly load — the number the planner divides the syllabus by —
            fills in by itself, and keeps itself right every time the grid
            changes.
          </p>
          <Button type="submit" className="w-full"
            disabled={!ready || save.isPending}>
            {save.isPending ? "Adding…" : "Add subject"}
          </Button>
        </form>
      </Modal>
    </>
  );
}

// ── the hook the screens share ───────────────────────────────────────────────
export interface ClassSubjectPick {
  classes: SchoolClass[];
  classId: string;
  setClassId: (id: string) => void;
  subjects: ClassSubject[];
  csId: string;
  setCsId: (id: string) => void;
  subject: ClassSubject | undefined;
  /** class_id → how many subjects it has. Empty for a teacher, who is only
   *  ever shown classes she teaches a subject in. */
  subjectCount: Map<string, number>;
  loading: boolean;
}

/**
 * The effective pick: the user's choice while it is still valid, otherwise the
 * first thing available. Derived, never a `setState` in an effect — the version
 * of this that used one flickered through the wrong subject's chapters on every
 * class change.
 *
 * `mine` narrows CLASSES to the ones she teaches in. It is belt-and-braces: the
 * syllabus board is already a block server-side, so a teacher who somehow named
 * another class gets an empty board rather than someone else's.
 */
export function useClassSubject(yearId: string | null,
  { mine = false }: { mine?: boolean } = {}): ClassSubjectPick {
  const [pickedClass, setPickedClass] = useState("");
  const [pickedCs, setPickedCs] = useState("");

  const { data: raw = [], isLoading: cl } = useQuery({
    queryKey: ["classes", yearId, mine ? "mine" : "all"],
    queryFn: () => schoolApi.classes(yearId!, mine || undefined),
    enabled: !!yearId,
  });

  /**
   * School order, not string order.
   *
   * The server sorts by `SchoolClass.name`, which is TEXT — so a school with a
   * class 11 and a class 3 reads "11, 12, 3, 5, 7". Numeric-aware collation is
   * the whole fix, and it belongs here rather than in a migration because
   * "10-B" is a name, not a number, and only the reader needs it ordered.
   */
  const classes = useMemo(() => sortClasses(raw), [raw]);

  // How many subjects each class has. One read for the year (the batched feed
  // `S-77` added), and ADMIN ONLY: `/academics/class-subjects` is not narrowed
  // per teacher, so asking for it as one would hand her the whole school's
  // assignments. A teacher does not need it — every class in her list is a
  // class she teaches a subject in, so none of them is empty.
  const { data: yearWide } = useQuery({
    queryKey: ["all-class-subjects", yearId],
    queryFn: () => schoolApi.allClassSubjects(yearId ?? undefined),
    enabled: !!yearId && !mine,
  });
  const countFor = useMemo(() => {
    const m = new Map<string, number>();
    for (const cs of yearWide ?? []) {
      m.set(cs.class_id, (m.get(cs.class_id) ?? 0) + 1);
    }
    return m;
  }, [yearWide]);

  /**
   * The default class is the first one that HAS subjects.
   *
   * Landing on `classes[0]` put this school on 11-A, which its import left with
   * no subjects at all — so the page opened on a dead end every time and the
   * six classes that do have chapters were one click away and invisible. An
   * empty class is still listed and still pickable; it is just not where
   * somebody is dropped.
   */
  const firstUseful = countFor.size
    ? (classes.find((c) => (countFor.get(c.id) ?? 0) > 0) ?? classes[0])
    : classes[0];
  const classId = classes.some((c) => c.id === pickedClass)
    ? pickedClass : (firstUseful?.id ?? "");

  // `mine` narrows to HER subjects. Server-side, like the class list above:
  // her picker used to offer every subject of the class, so most of her chips
  // opened a board the server then (correctly) refused to fill.
  const { data: subjects = [], isLoading: sl } = useQuery({
    queryKey: ["class-subjects", classId, mine ? "mine" : "all"],
    queryFn: () => schoolApi.classSubjects(classId, mine || undefined),
    enabled: !!classId,
  });
  const csId = subjects.some((s) => s.id === pickedCs)
    ? pickedCs : (subjects[0]?.id ?? "");

  return {
    classes, classId, setClassId: setPickedClass,
    subjects, csId, setCsId: setPickedCs,
    subject: subjects.find((s) => s.id === csId),
    subjectCount: countFor,
    loading: cl || sl,
  };
}

/**
 * The class row on its own — for screens that pick a class and nothing else.
 *
 * Built for the Timetable tab, where the class lived in a `<select>` narrow
 * enough that a school could not see how many classes it had, and reaching one
 * meant opening a menu and reading it in string order (`11, 12, 3, 5`). The
 * grid below it is the whole screen; the thing that chooses which grid you are
 * looking at should be as legible as a tab bar, because that is what it is.
 */
export function ClassTabs({ classes, classId, onChange, className }: {
  classes: SchoolClass[];
  classId: string;
  onChange: (id: string) => void;
  className?: string;
}) {
  const sorted = useMemo(() => sortClasses(classes), [classes]);
  if (!sorted.length) return null;
  return (
    // `flex-1` is load-bearing, not decoration. `contain: inline-size` makes an
    // element's width independent of its contents — which is the point, it stops
    // a long chip row widening the page — but it means the width has to come
    // from OUTSIDE. Without `flex-1` this box computed to zero, `overflow-x:
    // auto` clipped to that zero, and every chip rendered into the DOM at a real
    // position and painted nowhere: a labelled empty box on Timetable. The
    // picker's own rows always had `flex-1`; this one was copied without it.
    <div className={cn("flex min-w-0 flex-1 gap-1.5 overflow-x-auto pb-0.5", className)}
      style={{ contain: "layout inline-size" }}>
      {sorted.map((c) => (
        <Chip key={c.id} active={c.id === classId} onClick={() => onChange(c.id)}
          label={classLabel(c)} />
      ))}
    </div>
  );
}

// ── the two rows ─────────────────────────────────────────────────────────────
export function ClassSubjectPicker({ pick, yearId, canAdd, teacherFor }: {
  pick: ClassSubjectPick;
  yearId: string | null;
  /** Admin. A teacher navigates the same rows and adds nothing. */
  canAdd: boolean;
  /** member_id → name, so a subject chip can name its mentor. */
  teacherFor?: Map<string, string>;
}) {
  const qc = useQueryClient();
  const { classes, classId, setClassId, subjects, csId, setCsId } = pick;

  return (
    <div className="mb-4 space-y-2 rounded-xl border border-border bg-card p-3">
      <Row label="Class"
        action={canAdd ? (
          <AddClass yearId={yearId} onAdded={(c) => {
            qc.invalidateQueries({ queryKey: ["classes"] });
            setClassId(c.id);
          }} />
        ) : null}>
        {classes.length ? classes.map((c) => {
          // A class with no subjects is a real gap in the setup, and the chip
          // row is where somebody notices it. Marked, never hidden — hiding it
          // is how it stays unfixed until a teacher cannot log a lesson.
          const empty = pick.subjectCount.size
            && !(pick.subjectCount.get(c.id) ?? 0);
          return (
            <Chip key={c.id} active={c.id === classId} onClick={() => setClassId(c.id)}
              label={classLabel(c)} caption={empty ? "no subjects" : null} />
          );
        }) : (
          // Loading and empty are different facts and must not share a
          // sentence: telling an admin "No classes yet" while the request is
          // still in flight invites her to create classes she already has.
          <span className="py-1.5 text-sm text-muted-foreground">
            {pick.loading ? "Loading classes…"
              : canAdd ? "No classes yet — add the first one."
                : "You are not assigned to any class yet."}
          </span>
        )}
      </Row>

      <Row label="Subject"
        action={canAdd && classId ? (
          <AddSubject classId={classId} onAdded={(cs) => {
            qc.invalidateQueries({ queryKey: ["class-subjects", classId] });
            setCsId(cs.id);
          }} />
        ) : null}>
        {subjects.length ? subjects.map((s) => (
          <Chip key={s.id} active={s.id === csId} onClick={() => setCsId(s.id)}
            label={s.subject_name ?? "Subject"}
            caption={s.teacher_member_id
              ? teacherFor?.get(s.teacher_member_id) ?? null
              // Never blank: an unassigned subject is a real gap in the setup
              // and the picker is where somebody notices it.
              : "no mentor"} />
        )) : (
          <span className="py-1.5 text-sm text-muted-foreground">
            {pick.loading ? "Loading subjects…"
              : classId
                ? canAdd
                  ? "This class has no subjects yet — add one."
                  : "This class has no subjects set up yet."
                : "Pick a class first."}
          </span>
        )}
      </Row>
    </div>
  );
}
