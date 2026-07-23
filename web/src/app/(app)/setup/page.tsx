"use client";

import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, GraduationCap, Plus, Star, Trash2, Users } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ClassSubjectsPanel } from "@/components/school/class-subjects-panel";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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

  return (
    <Card title="Academic years">
      {years.map((y) => (
        <Row key={y.id} onDelete={canEdit ? () => remove.mutate(y.id) : undefined}>
          <span className="font-medium">{y.label}</span>
          <span className="ml-2 text-xs text-muted-foreground">{y.start_date} → {y.end_date}</span>
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

const classLabel = (c: SchoolClass) => c.name + (c.section ? `-${c.section}` : "");

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
          {openId === c.id ? <ClassSubjectsPanel classId={c.id} canEdit={canEdit} /> : null}
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

/** By-teacher view: pick a teacher, see everything on their plate — classes,
 * subjects, weekly period load, and which classes they're class-teacher of. */
function ByTeacherView({ classes }: { classes: SchoolClass[] }) {
  const { data: membersData } = useQuery({ queryKey: ["members"], queryFn: appApi.members });
  const staff = (membersData?.members ?? []).filter((m) => m.member_id);
  const [picked, setPicked] = useState("");
  const teacherId = staff.some((t) => t.member_id === picked) ? picked : (staff[0]?.member_id ?? "");

  const results = useQueries({
    queries: classes.map((c) => ({
      queryKey: ["class-subjects", c.id],
      queryFn: () => schoolApi.classSubjects(c.id),
    })),
  });
  const loading = results.some((r) => r.isLoading);

  type Row = { classId: string; classLabel: string; subject: string; ppw: number };
  const byTeacher = new Map<string, Row[]>();
  const unassigned: Row[] = [];
  classes.forEach((c, i) => {
    for (const cs of results[i]?.data ?? []) {
      const row = { classId: c.id, classLabel: classLabel(c), subject: cs.subject_name ?? "?", ppw: cs.periods_per_week };
      if (cs.teacher_member_id) {
        byTeacher.set(cs.teacher_member_id, [...(byTeacher.get(cs.teacher_member_id) ?? []), row]);
      } else {
        unassigned.push(row);
      }
    }
  });

  const rows = byTeacher.get(teacherId) ?? [];
  const totalPpw = rows.reduce((a, r) => a + r.ppw, 0);
  const classTeacherOf = classes.filter((c) => c.class_teacher_member_id === teacherId);

  if (!staff.length) return <p className="text-sm text-muted-foreground">No staff yet — add members first.</p>;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <select
          aria-label="Teacher"
          className="rounded-md border border-border bg-card px-2 py-1.5 text-sm"
          value={teacherId}
          onChange={(e) => setPicked(e.target.value)}
        >
          {staff.map((t) => (
            <option key={t.member_id} value={t.member_id!}>
              {t.name}{byTeacher.has(t.member_id!) ? ` · ${byTeacher.get(t.member_id!)!.length}` : ""}
            </option>
          ))}
        </select>
        <Badge tone="primary"><GraduationCap className="h-3 w-3" /> {rows.length} subject{rows.length === 1 ? "" : "s"}</Badge>
        <Badge tone={totalPpw > 48 ? "danger" : "neutral"}>{totalPpw} periods/week</Badge>
        {classTeacherOf.length ? (
          <Badge tone="success">class teacher of {classTeacherOf.map(classLabel).join(", ")}</Badge>
        ) : null}
      </div>

      {loading ? (
        <PageLoading label="Reading assignments…" />
      ) : rows.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-3 py-4 text-center text-sm text-muted-foreground">
          Nothing assigned yet — assign subjects from the class view.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
                <th className="px-3 py-2 font-medium">Class</th>
                <th className="px-3 py-2 font-medium">Subject</th>
                <th className="px-3 py-2 font-medium">Periods/week</th>
              </tr>
            </thead>
            <tbody>
              {rows
                .sort((a, b) => a.classLabel.localeCompare(b.classLabel) || a.subject.localeCompare(b.subject))
                .map((r, i) => (
                  <tr key={i} className="border-b border-border/60 bg-card last:border-0">
                    <td className="px-3 py-2 font-medium">{r.classLabel}</td>
                    <td className="px-3 py-2">{r.subject}</td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">{r.ppw || <span className="text-warning">not set</span>}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && unassigned.length ? (
        <p className="text-xs text-warning">
          {unassigned.length} subject{unassigned.length === 1 ? " has" : "s have"} no teacher:{" "}
          {unassigned.slice(0, 4).map((r) => `${r.classLabel} ${r.subject}`).join(", ")}
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
        <ByTeacherView classes={classes} />
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
  const canEdit = me?.org_role === "admin";
  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <PageHeader
          title="School setup"
          subtitle="The school's structure: who teaches what, plus years, subjects & categories"
        />
        <YearSwitcher />
      </div>
      <div className="grid gap-4">
        <AssignmentsCard canEdit={canEdit} />
        <div className="grid gap-4 lg:grid-cols-2">
          <YearsCard canEdit={canEdit} />
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
