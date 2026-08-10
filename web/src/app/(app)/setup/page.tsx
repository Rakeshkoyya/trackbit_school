"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, GraduationCap, Plus, Star, Trash2, Users } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ClassSubjectsPanel } from "@/components/school/class-subjects-panel";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InlineDate, InlineText } from "@/components/ui/inline-edit";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { PageLoading } from "@/components/ui/page-loading";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { SchoolClass } from "@/lib/school-types";
import { cn } from "@/lib/utils";

function Card({ title, action, children }: { title: string; action?: React.ReactNode; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold">{title}</h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function Row({ children, onDelete }: { children: React.ReactNode; onDelete?: () => void }) {
  return (
    <div className="flex items-center gap-2 border-t border-border py-2 text-sm first:border-t-0">
      <div className="min-w-0 flex-1">{children}</div>
      {onDelete ? (
        <button onClick={onDelete} aria-label="Delete" className="text-muted-foreground hover:text-danger">
          <Trash2 className="h-4 w-4" />
        </button>
      ) : null}
    </div>
  );
}

function YearsCard({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient();
  const { years } = useYear();
  const [label, setLabel] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [editTracking, setEditTracking] = useState<string | null>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["academic-years"] });

  const create = useMutation({
    mutationFn: () => schoolApi.createYear({ label: label.trim(), start_date: start, end_date: end }),
    onSuccess: () => { invalidate(); setLabel(""); setStart(""); setEnd(""); toast.success("Year added"); },
    onError: (e) => showApiError(e, "Could not add year"),
  });
  const activate = useMutation({
    mutationFn: (id: string) => schoolApi.activateYear(id),
    onSuccess: () => { invalidate(); toast.success("Active year updated"); },
    onError: (e) => showApiError(e, "Could not activate"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteYear(id),
    onSuccess: () => { invalidate(); toast.success("Year removed"); },
    onError: (e) => showApiError(e, "Could not remove"),
  });
  const setTracking = useMutation({
    mutationFn: ({ id, date }: { id: string; date: string | null }) =>
      schoolApi.updateYear(id, { tracking_start_date: date }),
    onSuccess: () => { invalidate(); setEditTracking(null); toast.success("Tracking start updated"); },
    onError: (e) => showApiError(e, "Could not update"),
  });
  // Label and window. `updateYear` has accepted these since P0-C; only the
  // tracking date was ever sent, so a year labelled "2026-2027" instead of
  // "2026-27" could be deleted but not corrected.
  const patch = useMutation({
    mutationFn: ({ id, body }: {
      id: string; body: { label?: string; start_date?: string; end_date?: string };
    }) => schoolApi.updateYear(id, body),
    onSuccess: () => { invalidate(); toast.success("Year updated"); },
    onError: (e) => showApiError(e, "Could not update year"),
  });

  return (
    <Card title="Academic years">
      {years.map((y) => (
        <Row key={y.id} onDelete={canEdit ? () => remove.mutate(y.id) : undefined}>
          <InlineText canEdit={canEdit} value={y.label} className="font-medium" width="w-28"
            onSave={(label) => patch.mutate({ id: y.id, body: { label } })} />
          <span className="ml-2 inline-flex items-center gap-1 text-xs text-muted-foreground">
            <InlineDate canEdit={canEdit} value={y.start_date}
              onSave={(start_date) => patch.mutate({ id: y.id, body: { start_date } })} />
            →
            <InlineDate canEdit={canEdit} value={y.end_date}
              onSave={(end_date) => patch.mutate({ id: y.id, body: { end_date } })} />
          </span>
          {y.is_active ? (
            <span className="ml-2 inline-flex items-center gap-1 text-xs text-primary"><Star className="h-3 w-3" /> current</span>
          ) : canEdit ? (
            <button onClick={() => activate.mutate(y.id)} className="ml-2 text-xs text-primary hover:underline">
              make current
            </button>
          ) : null}
          {/* Mid-year adoption: everything before this date is "before our time" —
              excluded from plans and forecasts, shown as no-data, never warned about. */}
          {editTracking === y.id ? (
            <span className="ml-2 inline-flex items-center gap-1">
              <Input className="h-6 w-36 text-xs" type="date" autoFocus
                defaultValue={y.tracking_start_date ?? ""}
                onChange={(e) => setTracking.mutate({ id: y.id, date: e.target.value || null })} />
              <button onClick={() => setEditTracking(null)} className="text-xs text-muted-foreground hover:underline">done</button>
            </span>
          ) : (
            <button
              onClick={canEdit ? () => setEditTracking(y.id) : undefined}
              className={cn("ml-2 text-xs", canEdit ? "text-primary hover:underline" : "text-muted-foreground")}
              title="If the school adopted TrackBit mid-year, data before this date is treated as no-data (never a warning)."
            >
              {y.tracking_start_date ? `tracking from ${y.tracking_start_date}` : canEdit ? "set tracking start" : null}
            </button>
          )}
        </Row>
      ))}
      {canEdit ? (
        <form className="mt-3 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); if (label && start && end) create.mutate(); }}>
          <Input className="w-28" placeholder="2026-27" value={label} onChange={(e) => setLabel(e.target.value)} />
          <Input className="w-40" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          <Input className="w-40" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          <Button size="sm" type="submit" disabled={create.isPending || !label || !start || !end}>
            <Plus className="h-4 w-4" /> Add
          </Button>
        </form>
      ) : null}
    </Card>
  );
}

/** Terms — the missing half of the year (V1-13).
 *
 *  Terms were readable on five screens and creatable on none, so the only terms
 *  that ever existed were the seed's. That is not cosmetic: `syllabus_units.
 *  term_id` files a chapter under a term (V2-P11), band assessment refuses with
 *  *"Set up a term first"*, and `approve`/`draft` take a `term_id` — so a real
 *  school set up through the wizard could not plan term by term at all.
 *
 *  Deleting is guarded server-side (a term with plan approvals under it stays),
 *  which is why this offers no "edit dates": moving a term's window after its
 *  plans are approved would silently re-scope a locked baseline (P2). Since
 *  "a term IS its exam" (founder, 2026-08-08) the window is not this screen's to
 *  set anyway — `sync_terms_from_exams` derives it from the exam block, so the
 *  honest place to move a term is Plan → Exams.
 *
 *  The NAME is the school's own, and is editable here. It used to be overwritten
 *  to "Term 1"/"Term 2" by that same sync on every exam edit; that is fixed in
 *  `term_sync.py`, without which this rename would silently revert.
 */
function TermsCard({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const [name, setName] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const { data: terms = [] } = useQuery({
    queryKey: ["terms", yearId],
    queryFn: () => schoolApi.terms(yearId ?? undefined),
    enabled: !!yearId,
  });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["terms"] });

  const create = useMutation({
    mutationFn: () => schoolApi.createTerm({
      academic_year_id: yearId!, name: name.trim(), start_date: start, end_date: end,
    }),
    onSuccess: () => { invalidate(); setName(""); setStart(""); setEnd(""); toast.success("Term added"); },
    onError: (e) => showApiError(e, "Could not add term"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteTerm(id),
    onSuccess: () => { invalidate(); toast.success("Term removed"); },
    onError: (e) => showApiError(e, "Could not remove term"),
  });
  const rename = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) =>
      schoolApi.updateTerm(id, { name }),
    onSuccess: () => { invalidate(); toast.success("Term renamed"); },
    onError: (e) => showApiError(e, "Could not rename term"),
  });

  return (
    <Card title="Terms">
      {terms.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          No terms yet. A school that sizes each chapter when its term begins needs these —
          syllabus chapters, plan approval and band assessment are all filed under a term.
        </p>
      ) : null}
      {terms.map((t) => (
        <Row key={t.id} onDelete={canEdit ? () => remove.mutate(t.id) : undefined}>
          <InlineText canEdit={canEdit} value={t.name} className="font-medium" width="w-36"
            onSave={(name) => rename.mutate({ id: t.id, name })} />
          <span className="ml-2 text-xs text-muted-foreground">{t.start_date} → {t.end_date}</span>
        </Row>
      ))}
      {terms.length > 0 && canEdit ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Click a term&apos;s name to rename it. The dates come from its exam — a term ends on
          the last day of the exam that closes it, so move the exam on Plan → Exams.
        </p>
      ) : null}
      {canEdit ? (
        <form className="mt-3 flex flex-wrap gap-2" onSubmit={(e) => {
          e.preventDefault();
          if (yearId && name && start && end) create.mutate();
        }}>
          <Input className="w-32" placeholder="Term 1" value={name} onChange={(e) => setName(e.target.value)} />
          <Input className="w-40" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
          <Input className="w-40" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
          <Button size="sm" type="submit" disabled={create.isPending || !yearId || !name || !start || !end}>
            <Plus className="h-4 w-4" /> Add
          </Button>
        </form>
      ) : null}
    </Card>
  );
}

const classLabel = (c: SchoolClass) => c.name + (c.section ? `-${c.section}` : "");

/** D-03 (V1-2): who owns this class. The field has existed since P0-C and no
 * screen ever set it — which is why every absence row read "class teacher: —"
 * and every intervention was unassigned. */
function ClassTeacherPicker({ klass, canEdit }: { klass: SchoolClass; canEdit: boolean }) {
  const qc = useQueryClient();
  const { data: membersData } = useQuery({ queryKey: ["members"], queryFn: appApi.members });
  const staff = (membersData?.members ?? []).filter((m) => m.member_id);
  const save = useMutation({
    mutationFn: (memberId: string | null) =>
      schoolApi.updateClass(klass.id, { class_teacher_member_id: memberId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      toast.success("Class teacher set");
    },
    onError: (e) => showApiError(e, "Could not set the class teacher"),
  });
  const currentName = staff.find((t) => t.member_id === klass.class_teacher_member_id)?.name;

  if (!canEdit) {
    return (
      <p className="mb-2 text-xs text-muted-foreground">
        Class teacher: {currentName ?? "—"}
      </p>
    );
  }
  return (
    <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
      <span className="text-xs font-medium text-muted-foreground">Class teacher</span>
      <select
        aria-label={`Class teacher of ${classLabel(klass)}`}
        className="rounded-md border border-border bg-card px-2 py-1 text-sm"
        value={klass.class_teacher_member_id ?? ""}
        disabled={save.isPending}
        onChange={(e) => save.mutate(e.target.value || null)}
      >
        <option value="">— not assigned</option>
        {staff.map((t) => (
          <option key={t.member_id} value={t.member_id!}>{t.name}</option>
        ))}
      </select>
      {!klass.class_teacher_member_id ? (
        <span className="text-xs text-warning">absence follow-ups for this class have no owner</span>
      ) : null}
    </div>
  );
}

/** Renaming a class in place.
 *
 *  `updateClass` has accepted name and section since P0-C, and only the
 *  class-teacher picker ever called it — so a class typed "6" that should read
 *  "VI" could only be deleted, taking its subjects, syllabus, plans and timetable
 *  with it. Sits inside the expanded panel rather than on the row, where it would
 *  fight the show/hide toggle. */
function ClassRename({ klass, canEdit }: { klass: SchoolClass; canEdit: boolean }) {
  const qc = useQueryClient();
  const save = useMutation({
    mutationFn: (b: { name?: string; section?: string | null }) =>
      schoolApi.updateClass(klass.id, b),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["classes"] });
      toast.success("Class updated");
    },
    onError: (e) => showApiError(e, "Could not update class"),
  });
  if (!canEdit) return null;
  return (
    <div className="mt-2 flex items-center gap-2 text-sm">
      <span className="text-xs text-muted-foreground">Class</span>
      <InlineText canEdit value={klass.name} width="w-20"
        onSave={(name) => save.mutate({ name })} />
      <span className="text-xs text-muted-foreground">Section</span>
      <InlineText canEdit value={klass.section ?? ""} width="w-20" placeholder="none"
        onSave={(section) => save.mutate({ section })} />
    </div>
  );
}

/** By-class view: each class expands into its subject table (teacher, periods/week,
 * allocation bar, copy-from-section) — the same panel the wizard uses. */
function ByClassView({ classes, canEdit }: { classes: SchoolClass[]; canEdit: boolean }) {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const [name, setName] = useState("");
  const [section, setSection] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const invalidate = () => qc.invalidateQueries({ queryKey: ["classes"] });
  const create = useMutation({
    mutationFn: () => schoolApi.createClass({ academic_year_id: yearId!, name: name.trim(), section: section.trim() || null }),
    onSuccess: () => { invalidate(); setName(""); setSection(""); toast.success("Class added"); },
    onError: (e) => showApiError(e, "Could not add class"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteClass(id),
    onSuccess: () => { invalidate(); toast.success("Class removed"); },
    onError: (e) => showApiError(e, "Could not remove"),
  });

  function confirmRemove(c: SchoolClass) {
    if (window.confirm(`Delete class ${classLabel(c)}? Its subjects, syllabus, plans and timetable go with it.`)) {
      remove.mutate(c.id);
    }
  }

  return (
    <div>
      {classes.length === 0 ? <p className="text-sm text-muted-foreground">No classes for this year yet.</p> : null}
      {classes.map((c) => (
        <div key={c.id} className="border-t border-border py-2 first:border-t-0">
          <div className="flex items-center gap-2 text-sm">
            <button className="min-w-0 flex-1 text-left font-medium hover:text-primary" onClick={() => setOpenId(openId === c.id ? null : c.id)}>
              {classLabel(c)}{" "}
              <span className="text-xs font-normal text-muted-foreground">
                {openId === c.id ? "· hide subjects" : "· show subjects & teachers"}
              </span>
            </button>
            {canEdit ? (
              <button onClick={() => confirmRemove(c)} aria-label={`Delete ${classLabel(c)}`} className="text-muted-foreground hover:text-danger">
                <Trash2 className="h-4 w-4" />
              </button>
            ) : null}
          </div>
          {openId === c.id ? (
            <>
              <ClassRename klass={c} canEdit={canEdit} />
              <ClassTeacherPicker klass={c} canEdit={canEdit} />
              <ClassSubjectsPanel classId={c.id} canEdit={canEdit} />
            </>
          ) : null}
        </div>
      ))}
      {canEdit ? (
        <form className="mt-3 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); if (name && yearId) create.mutate(); }}>
          <Input className="w-24" placeholder="Class (6)" value={name} onChange={(e) => setName(e.target.value)} />
          <Input className="w-28" placeholder="Section (B)" value={section} onChange={(e) => setSection(e.target.value)} />
          <Button size="sm" type="submit" disabled={create.isPending || !name || !yearId}>
            <Plus className="h-4 w-4" /> Add class
          </Button>
        </form>
      ) : null}
    </div>
  );
}

/** By-teacher view — WRITABLE (V1-2, D-28/S-77): pick a teacher, tick the
 * class-subjects they take, save many at once. The smallest change with the
 * largest effect on setup time. One batched read for the whole year (the old
 * view fired a query per class to draw one screen). */
function ByTeacherView({ classes, canEdit }: { classes: SchoolClass[]; canEdit: boolean }) {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const { data: membersData } = useQuery({ queryKey: ["members"], queryFn: appApi.members });
  const staff = (membersData?.members ?? []).filter((m) => m.member_id);
  const [picked, setPicked] = useState("");
  const teacherId = staff.some((t) => t.member_id === picked) ? picked : (staff[0]?.member_id ?? "");

  const { data: allCs = [], isLoading: loading } = useQuery({
    queryKey: ["all-class-subjects", yearId],
    queryFn: () => schoolApi.allClassSubjects(yearId ?? undefined),
    enabled: !!yearId,
  });

  const nameOf = new Map(staff.map((t) => [t.member_id!, t.name]));
  const mineIds = new Set(allCs.filter((cs) => cs.teacher_member_id === teacherId).map((cs) => cs.id));
  const [draft, setDraft] = useState<Set<string> | null>(null);
  const checked = draft ?? mineIds;
  const toggle = (id: string) => {
    const next = new Set(checked);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setDraft(next);
  };

  const save = useMutation({
    mutationFn: async () => {
      const adds = [...checked].filter((id) => !mineIds.has(id));
      const removes = [...mineIds].filter((id) => !checked.has(id));
      await Promise.all([
        ...adds.map((id) => schoolApi.updateClassSubject(id, { teacher_member_id: teacherId })),
        ...removes.map((id) => schoolApi.updateClassSubject(id, { teacher_member_id: null })),
      ]);
      return adds.length + removes.length;
    },
    onSuccess: (n) => {
      qc.invalidateQueries({ queryKey: ["all-class-subjects"] });
      qc.invalidateQueries({ queryKey: ["class-subjects"] });
      setDraft(null);
      toast.success(`${n} assignment${n === 1 ? "" : "s"} updated`);
    },
    onError: (e) => {
      showApiError(e, "Could not save assignments");
      qc.invalidateQueries({ queryKey: ["all-class-subjects"] });
      setDraft(null);
    },
  });

  const shown = allCs.filter((cs) => checked.has(cs.id));
  const totalPpw = shown.reduce((a, r) => a + r.periods_per_week, 0);
  const classTeacherOf = classes.filter((c) => c.class_teacher_member_id === teacherId);
  const unassigned = allCs.filter((cs) => !cs.teacher_member_id && !checked.has(cs.id));

  if (!staff.length) return <p className="text-sm text-muted-foreground">No staff yet — add members first.</p>;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Teacher"
          className="rounded-md border border-border bg-card px-2 py-1.5 text-sm"
          value={teacherId}
          onChange={(e) => { setPicked(e.target.value); setDraft(null); }}
        >
          {staff.map((t) => (
            <option key={t.member_id} value={t.member_id!}>{t.name}</option>
          ))}
        </select>
        <Badge tone="primary"><GraduationCap className="h-3 w-3" /> {shown.length} subject{shown.length === 1 ? "" : "s"}</Badge>
        <Badge tone={totalPpw > 48 ? "danger" : "neutral"}>{totalPpw} periods/week</Badge>
        {classTeacherOf.length ? (
          <Badge tone="success">class teacher of {classTeacherOf.map(classLabel).join(", ")}</Badge>
        ) : null}
        {draft !== null ? (
          <span className="ml-auto flex gap-2">
            <Button size="sm" onClick={() => save.mutate()} disabled={save.isPending}>
              {save.isPending ? "Saving…" : "Save assignments"}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setDraft(null)}>Cancel</Button>
          </span>
        ) : null}
      </div>

      {loading ? (
        <PageLoading label="Reading assignments…" />
      ) : allCs.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-3 py-4 text-center text-sm text-muted-foreground">
          No subjects on any class yet — add them from the class view first.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                {canEdit ? <th className="w-8 px-3 py-2" aria-label="Teaches" /> : null}
                <th className="px-3 py-2 font-medium">Class</th>
                <th className="px-3 py-2 font-medium">Subject</th>
                <th className="px-3 py-2 font-medium">Periods/week</th>
                <th className="px-3 py-2 font-medium">Currently</th>
              </tr>
            </thead>
            <tbody>
              {allCs.map((cs) => {
                const isChecked = checked.has(cs.id);
                const current = cs.teacher_member_id ? (nameOf.get(cs.teacher_member_id) ?? "—") : null;
                return (
                  <tr key={cs.id}
                    onClick={canEdit ? () => toggle(cs.id) : undefined}
                    className={`border-b border-border/60 last:border-0 ${isChecked ? "bg-primary/5" : "bg-card"} ${canEdit ? "cursor-pointer hover:bg-muted/30" : ""}`}>
                    {canEdit ? (
                      <td className="px-3 py-2">
                        <input type="checkbox" readOnly checked={isChecked}
                          className="h-4 w-4 accent-[var(--primary)]" aria-label={`${cs.class_label} ${cs.subject_name}`} />
                      </td>
                    ) : null}
                    <td className="px-3 py-2 font-medium">{cs.class_label}</td>
                    <td className="px-3 py-2">{cs.subject_name}</td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {cs.periods_per_week || <span className="text-warning">not set</span>}
                    </td>
                    <td className="px-3 py-2 text-xs text-muted-foreground">
                      {cs.teacher_member_id === teacherId ? "this teacher"
                        : current ?? <span className="text-warning">nobody</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {!loading && unassigned.length ? (
        <p className="text-xs text-warning">
          {unassigned.length} subject{unassigned.length === 1 ? " has" : "s have"} no teacher:{" "}
          {unassigned.slice(0, 4).map((r) => `${r.class_label} ${r.subject_name}`).join(", ")}
          {unassigned.length > 4 ? ` +${unassigned.length - 4} more` : ""}
        </p>
      ) : null}
    </div>
  );
}

/** Who teaches what — the page's centrepiece. Two lenses over the same data:
 * a class's subject table, or a teacher's full plate. */
function AssignmentsCard({ canEdit }: { canEdit: boolean }) {
  const { yearId } = useYear();
  const [view, setView] = useState<"class" | "teacher">("class");
  const { data: classes = [], isLoading } = useQuery({
    queryKey: ["classes", yearId],
    queryFn: () => schoolApi.classes(yearId ?? undefined),
    enabled: !!yearId,
  });

  return (
    <Card
      title="Teaching assignments"
      action={
        <div className="flex gap-1 rounded-lg border border-border p-0.5">
          {([["class", "By class", GraduationCap], ["teacher", "By teacher", Users]] as const).map(([key, label, Icon]) => (
            <button
              key={key}
              type="button"
              onClick={() => setView(key)}
              className={cn(
                "flex items-center gap-1 rounded-md px-2.5 py-1 text-xs transition-colors",
                view === key ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted",
              )}
            >
              <Icon className="h-3.5 w-3.5" /> {label}
            </button>
          ))}
        </div>
      }
    >
      {isLoading ? (
        <PageLoading label="Loading classes…" />
      ) : view === "class" ? (
        <ByClassView classes={classes} canEdit={canEdit} />
      ) : (
        <ByTeacherView classes={classes} canEdit={canEdit} />
      )}
    </Card>
  );
}

function SimpleListCard({
  title, queryKey, list, create, remove, placeholder, canEdit, seed,
}: {
  title: string;
  queryKey: string[];
  list: () => Promise<{ id: string; name: string }[]>;
  create: (name: string) => Promise<unknown>;
  remove: (id: string) => Promise<unknown>;
  placeholder: string;
  canEdit: boolean;
  seed?: () => Promise<unknown>;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const { data = [] } = useQuery({ queryKey, queryFn: list });
  const invalidate = () => qc.invalidateQueries({ queryKey });
  const add = useMutation({
    mutationFn: () => create(name.trim()),
    onSuccess: () => { invalidate(); setName(""); toast.success("Added"); },
    onError: (e) => showApiError(e, "Could not add"),
  });
  const del = useMutation({
    mutationFn: (id: string) => remove(id),
    onSuccess: () => { invalidate(); toast.success("Removed"); },
    onError: (e) => showApiError(e, "Could not remove"),
  });
  const seedM = useMutation({
    mutationFn: () => seed!(),
    onSuccess: () => { invalidate(); toast.success("Defaults added"); },
    onError: (e) => showApiError(e, "Could not seed"),
  });

  return (
    <Card
      title={title}
      action={canEdit && seed && data.length === 0 ? (
        <Button size="sm" variant="ghost" onClick={() => seedM.mutate()}><Check className="h-4 w-4" /> Add defaults</Button>
      ) : undefined}
    >
      {data.map((x) => (
        <Row key={x.id} onDelete={canEdit ? () => del.mutate(x.id) : undefined}>
          <span className="font-medium">{x.name}</span>
        </Row>
      ))}
      {canEdit ? (
        <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (name.trim()) add.mutate(); }}>
          <Input placeholder={placeholder} value={name} onChange={(e) => setName(e.target.value)} />
          <Button size="sm" type="submit" disabled={add.isPending || !name.trim()}><Plus className="h-4 w-4" /> Add</Button>
        </form>
      ) : null}
    </Card>
  );
}

function AcademicsInner() {
  const { me } = useAuth();
  // SETUP-REDESIGN-PLAN §6: structure is ours to change once the school is live.
  // The operator keeps editing (they are super-admin); the school reads.
  // Everything stays VISIBLE — D-2 is that the admin sees all the data, and
  // only the write affordance goes.
  const handedOver = Boolean(me?.org?.handed_over_at);
  const frozen = handedOver && !me?.is_super_admin;
  const canEdit = me?.org_role === "admin" && !frozen;
  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <PageHeader
          title="School setup"
          subtitle="The school's structure: who teaches what, plus years, subjects & categories"
        />
        <YearSwitcher />
      </div>
      {frozen ? (
        <div className="mb-4 rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
          This is your school&apos;s structure, and TrackBit maintains it. Tell us
          what needs to change — a new class, a subject, a teacher&apos;s
          allocation — and we will make it. Adding students and staff, and
          everything you do day to day, is unchanged.
        </div>
      ) : null}
      <div className="grid gap-4">
        <AssignmentsCard canEdit={canEdit} />
        <div className="grid gap-4 lg:grid-cols-2">
          <YearsCard canEdit={canEdit} />
          <TermsCard canEdit={canEdit} />
          <SimpleListCard
            title="Subjects" queryKey={["subjects"]} placeholder="Mathematics" canEdit={canEdit}
            list={schoolApi.subjects} create={schoolApi.createSubject} remove={schoolApi.deleteSubject}
          />
          <SimpleListCard
            title="Fee categories" queryKey={["categories"]} placeholder="Day Scholar" canEdit={canEdit}
            list={schoolApi.categories} create={schoolApi.createCategory} remove={schoolApi.deleteCategory}
            seed={schoolApi.seedCategories}
          />
          <SimpleListCard
            title="Skill areas (diagnostic)" queryKey={["skill-areas"]} placeholder="Reading" canEdit={canEdit}
            list={schoolApi.skillAreas} create={schoolApi.createSkill} remove={schoolApi.deleteSkill}
            seed={schoolApi.seedSkills}
          />
        </div>
      </div>
    </div>
  );
}

export default function SetupAcademicsPage() {
  return (
    <AuthGuard requireRole="admin">
      <AcademicsInner />
    </AuthGuard>
  );
}
