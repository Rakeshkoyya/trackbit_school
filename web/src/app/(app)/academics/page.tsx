"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Plus, Star, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

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

function ClassSubjectsPanel({ classId, canEdit }: { classId: string; canEdit: boolean }) {
  const qc = useQueryClient();
  const [subjectId, setSubjectId] = useState("");
  const [teacherId, setTeacherId] = useState("");
  const [periods, setPeriods] = useState("5");
  const { data: rows = [] } = useQuery({ queryKey: ["class-subjects", classId], queryFn: () => schoolApi.classSubjects(classId) });
  const { data: subjects = [] } = useQuery({ queryKey: ["subjects"], queryFn: schoolApi.subjects });
  const { data: membersData } = useQuery({ queryKey: ["members"], queryFn: appApi.members });
  const teachers = (membersData?.members ?? []).filter((m) => m.member_id && m.role !== "office");
  const invalidate = () => qc.invalidateQueries({ queryKey: ["class-subjects", classId] });
  const add = useMutation({
    mutationFn: () => schoolApi.addClassSubject({ class_id: classId, subject_id: subjectId, teacher_member_id: teacherId || null, periods_per_week: Number(periods) }),
    onSuccess: () => { invalidate(); setSubjectId(""); setTeacherId(""); toast.success("Subject added"); },
    onError: (e) => showApiError(e, "Could not add"),
  });
  const del = useMutation({ mutationFn: (id: string) => schoolApi.deleteClassSubject(id), onSuccess: invalidate });
  const teacherName = (mid: string | null) => teachers.find((t) => t.member_id === mid)?.name;

  return (
    <div className="mt-2 rounded-md bg-muted/30 p-2">
      {rows.length === 0 ? <p className="px-1 py-1 text-xs text-muted-foreground">No subjects yet.</p> : null}
      {rows.map((cs) => (
        <div key={cs.id} className="flex items-center gap-2 px-1 py-1 text-sm">
          <span className="flex-1">{cs.subject_name} <span className="text-xs text-muted-foreground">· {cs.periods_per_week}p/wk{cs.teacher_member_id ? ` · ${teacherName(cs.teacher_member_id) ?? "teacher"}` : ""}</span></span>
          {canEdit ? <button onClick={() => del.mutate(cs.id)} className="text-muted-foreground hover:text-danger"><Trash2 className="h-3.5 w-3.5" /></button> : null}
        </div>
      ))}
      {canEdit ? (
        <form className="mt-1 flex flex-wrap items-center gap-1.5" onSubmit={(e) => { e.preventDefault(); if (subjectId) add.mutate(); }}>
          <select className="rounded border border-border bg-card px-1.5 py-1 text-sm" value={subjectId} onChange={(e) => setSubjectId(e.target.value)}>
            <option value="">Subject…</option>
            {subjects.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <select className="rounded border border-border bg-card px-1.5 py-1 text-sm" value={teacherId} onChange={(e) => setTeacherId(e.target.value)}>
            <option value="">Teacher…</option>
            {teachers.map((t) => <option key={t.member_id} value={t.member_id!}>{t.name}</option>)}
          </select>
          <Input className="h-8 w-14" type="number" value={periods} onChange={(e) => setPeriods(e.target.value)} />
          <Button size="sm" type="submit" disabled={add.isPending || !subjectId}>Add</Button>
        </form>
      ) : null}
    </div>
  );
}

function ClassesCard({ canEdit }: { canEdit: boolean }) {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const [name, setName] = useState("");
  const [section, setSection] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const { data: classes = [] } = useQuery({
    queryKey: ["classes", yearId],
    queryFn: () => schoolApi.classes(yearId ?? undefined),
    enabled: !!yearId,
  });
  const invalidate = () => qc.invalidateQueries({ queryKey: ["classes", yearId] });
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

  return (
    <Card title="Classes & sections">
      {classes.length === 0 ? <p className="text-sm text-muted-foreground">No classes for this year yet.</p> : null}
      {classes.map((c) => (
        <div key={c.id} className="border-t border-border py-2 first:border-t-0">
          <div className="flex items-center gap-2 text-sm">
            <button className="min-w-0 flex-1 text-left font-medium hover:text-primary" onClick={() => setOpenId(openId === c.id ? null : c.id)}>
              {c.name}{c.section ? `-${c.section}` : ""} <span className="text-xs font-normal text-muted-foreground">· subjects</span>
            </button>
            {canEdit ? (
              <button onClick={() => remove.mutate(c.id)} aria-label="Delete" className="text-muted-foreground hover:text-danger">
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
            <Plus className="h-4 w-4" /> Add
          </Button>
        </form>
      ) : null}
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
  const canEdit = me?.org_role === "admin" || me?.org_role === "coordinator";
  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <PageHeader title="School setup" subtitle="Academic years, classes, subjects & fee categories" />
        <YearSwitcher />
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <YearsCard canEdit={canEdit} />
        <ClassesCard canEdit={canEdit} />
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
  );
}

export default function AcademicsPage() {
  return (
    <AuthGuard allow={["admin", "coordinator", "teacher"]}>
      <AcademicsInner />
    </AuthGuard>
  );
}
