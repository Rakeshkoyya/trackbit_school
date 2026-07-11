"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil, Plus, Search, Trash2, Upload, UserPlus } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { TIER_TONE } from "@/components/school/assessments";
import { Dropdown } from "@/components/school/student-table";
import { TimelineBlock } from "@/components/students/timeline-block";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Sheet } from "@/components/ui/sheet";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { RosterAnalyze, StudentListItem } from "@/lib/school-types";

function AddStudentSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const [form, setForm] = useState({ admission_no: "", full_name: "", roll_no: "", class_id: "", category_id: "" });
  const [g, setG] = useState({ name: "", phone: "", relation: "" });
  const { data: classes = [] } = useQuery({ queryKey: ["classes", yearId], queryFn: () => schoolApi.classes(yearId ?? undefined), enabled: !!yearId });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: schoolApi.categories });

  const create = useMutation({
    mutationFn: () => schoolApi.createStudent({
      admission_no: form.admission_no.trim(),
      full_name: form.full_name.trim(),
      roll_no: form.roll_no.trim() || null,
      class_id: form.class_id || null,
      category_id: form.category_id || null,
      guardians: g.name.trim() && g.phone.trim()
        ? [{ name: g.name.trim(), phone: g.phone.trim(), relation: g.relation.trim() || null, is_primary: true }]
        : [],
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success("Student added");
      setForm({ admission_no: "", full_name: "", roll_no: "", class_id: "", category_id: "" });
      setG({ name: "", phone: "", relation: "" });
      onOpenChange(false);
    },
    onError: (e) => showApiError(e, "Could not add student"),
  });

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Add student">
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (form.admission_no && form.full_name) create.mutate(); }}>
        <div className="grid grid-cols-2 gap-2">
          <div><Label>Admission no.</Label><Input value={form.admission_no} onChange={(e) => setForm({ ...form, admission_no: e.target.value })} required /></div>
          <div><Label>Roll no.</Label><Input value={form.roll_no} onChange={(e) => setForm({ ...form, roll_no: e.target.value })} /></div>
        </div>
        <div><Label>Full name</Label><Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required /></div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label>Class</Label>
            <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })}>
              <option value="">—</option>
              {classes.map((c) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
            </select>
          </div>
          <div>
            <Label>Category</Label>
            <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
              <option value="">—</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
        </div>
        <div className="rounded-md border border-border p-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">Primary guardian (optional)</p>
          <div className="grid grid-cols-2 gap-2">
            <Input placeholder="Name" value={g.name} onChange={(e) => setG({ ...g, name: e.target.value })} />
            <Input placeholder="Phone" value={g.phone} onChange={(e) => setG({ ...g, phone: e.target.value })} />
          </div>
          <Input className="mt-2" placeholder="Relation (Father/Mother)" value={g.relation} onChange={(e) => setG({ ...g, relation: e.target.value })} />
        </div>
        <Button type="submit" className="w-full" disabled={create.isPending || !form.admission_no || !form.full_name}>
          {create.isPending ? "Saving…" : "Add student"}
        </Button>
      </form>
    </Sheet>
  );
}

function EditStudentForm({ data, onSaved }: { data: import("@/lib/school-types").StudentDetail; onSaved: () => void }) {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const { data: classes = [] } = useQuery({ queryKey: ["classes", yearId], queryFn: () => schoolApi.classes(yearId ?? undefined), enabled: !!yearId });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: schoolApi.categories });
  const [form, setForm] = useState({
    full_name: data.full_name,
    roll_no: data.roll_no ?? "",
    class_id: data.class_id ?? "",
    category_id: data.category_id ?? "",
    status: data.status,
  });

  const save = useMutation({
    mutationFn: () => schoolApi.updateStudent(data.id, {
      full_name: form.full_name.trim(),
      roll_no: form.roll_no.trim() || null,
      class_id: form.class_id || null,
      category_id: form.category_id || null,
      status: form.status,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["students"] });
      qc.invalidateQueries({ queryKey: ["student", data.id] });
      toast.success("Saved");
      onSaved();
    },
    onError: (e) => showApiError(e, "Could not save"),
  });

  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (form.full_name.trim()) save.mutate(); }}>
      <div><Label>Full name</Label><Input value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required /></div>
      <div className="grid grid-cols-2 gap-2">
        <div><Label>Roll no.</Label><Input value={form.roll_no} onChange={(e) => setForm({ ...form, roll_no: e.target.value })} /></div>
        <div>
          <Label>Status</Label>
          <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}>
            <option value="active">active</option>
            <option value="left">left</option>
          </select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div>
          <Label>Class</Label>
          <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={form.class_id} onChange={(e) => setForm({ ...form, class_id: e.target.value })}>
            <option value="">Unassigned</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
          </select>
        </div>
        <div>
          <Label>Category</Label>
          <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm" value={form.category_id} onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
            <option value="">—</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
      </div>
      <Button type="submit" className="w-full" disabled={save.isPending || !form.full_name.trim()}>
        {save.isPending ? "Saving…" : "Save changes"}
      </Button>
    </form>
  );
}

function StudentDetailSheet({ id, onClose, canEdit }: { id: string | null; onClose: () => void; canEdit: boolean }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const { data } = useQuery({ queryKey: ["student", id], queryFn: () => schoolApi.student(id!), enabled: !!id });
  const remove = useMutation({
    mutationFn: () => schoolApi.deleteStudent(id!),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["students"] }); toast.success("Student removed"); onClose(); },
    onError: (e) => showApiError(e, "Could not remove"),
  });
  return (
    <Sheet open={!!id} onOpenChange={(v) => { if (!v) { setEditing(false); onClose(); } }} title={data?.full_name ?? "Student"}>
      {data && editing ? (
        <EditStudentForm data={data} onSaved={() => setEditing(false)} />
      ) : data ? (
        <div className="space-y-4 text-sm">
          <div className="flex flex-wrap gap-x-6 gap-y-1">
            <p><span className="text-muted-foreground">Admission</span> {data.admission_no}</p>
            {data.roll_no ? <p><span className="text-muted-foreground">Roll</span> {data.roll_no}</p> : null}
            <p><span className="text-muted-foreground">Class</span> {data.class_label ?? "—"}</p>
            <p><span className="text-muted-foreground">Category</span> {data.category_name ?? "—"}</p>
            <p><Badge tone={data.status === "active" ? "primary" : "neutral"}>{data.status}</Badge></p>
          </div>
          {canEdit ? (
            <Button variant="outline" size="sm" onClick={() => setEditing(true)}>
              <Pencil className="h-3.5 w-3.5" /> Edit details
            </Button>
          ) : null}
          <div>
            <p className="mb-1 font-medium">Guardians</p>
            {data.guardians.length === 0 ? (
              <p className="text-muted-foreground">None recorded.</p>
            ) : (
              <ul className="space-y-1">
                {data.guardians.map((gd) => (
                  <li key={gd.id} className="flex items-center gap-2">
                    <span className="font-medium">{gd.name}</span>
                    <span className="text-muted-foreground">{gd.relation ?? ""} · {gd.phone}</span>
                    {gd.is_primary ? <Badge>primary</Badge> : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <TimelineBlock studentId={data.id} />
          {canEdit ? (
            <Button variant="outline" className="w-full text-danger" onClick={() => remove.mutate()}>
              <Trash2 className="h-4 w-4" /> Remove student
            </Button>
          ) : null}
        </div>
      ) : null}
    </Sheet>
  );
}

function ImportSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const [analysis, setAnalysis] = useState<RosterAnalyze | null>(null);

  const analyze = useMutation({
    mutationFn: (file: File) => schoolApi.importRosterAnalyze(file),
    onSuccess: setAnalysis,
    onError: (e) => showApiError(e, "Could not read the file"),
  });
  const commit = useMutation({
    mutationFn: () =>
      schoolApi.importRosterCommit({ mapping: analysis!.mapping, rows: analysis!.rows, academic_year_id: yearId }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success(`Imported ${res.created} · skipped ${res.skipped}`);
      setAnalysis(null);
      onOpenChange(false);
    },
    onError: (e) => showApiError(e, "Import failed"),
  });

  return (
    <Sheet open={open} onOpenChange={(v) => { if (!v) setAnalysis(null); onOpenChange(v); }} title="Import roster (.xlsx)">
      {!analysis ? (
        <div className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Upload your student register. Columns are matched automatically — review before importing.
          </p>
          <input
            type="file" accept=".xlsx"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) analyze.mutate(f); }}
            className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-2 file:text-primary-foreground"
          />
          {analyze.isPending ? <p className="text-sm text-muted-foreground">Reading…</p> : null}
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm"><span className="font-medium">{analysis.row_count}</span> rows found. Detected columns:</p>
          <ul className="space-y-1 text-sm">
            {Object.entries(analysis.mapping).map(([field, col]) => (
              <li key={field} className="flex justify-between border-b border-border py-1">
                <span className="text-muted-foreground">{field.replace(/_/g, " ")}</span>
                <span className="font-medium">{col}</span>
              </li>
            ))}
          </ul>
          {!analysis.mapping.full_name || !analysis.mapping.admission_no ? (
            <p className="text-sm text-warning">Name and admission no. columns are required to import.</p>
          ) : null}
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={() => setAnalysis(null)}>Back</Button>
            <Button
              className="flex-1"
              disabled={commit.isPending || !analysis.mapping.full_name || !analysis.mapping.admission_no}
              onClick={() => commit.mutate()}
            >
              {commit.isPending ? "Importing…" : `Import ${analysis.row_count}`}
            </Button>
          </div>
        </div>
      )}
    </Sheet>
  );
}

const GROUP_COLORS = ["#6b7fd7", "#3f8f6b", "#c98a3d", "#b05f8a", "#5b9aa9", "#8a6bbf"];
type DirGroupBy = "class" | "category" | "status" | "band" | "none";

function StudentsInner() {
  const router = useRouter();
  const { me } = useAuth();
  const { yearId } = useYear();
  const canEdit = me?.org_role === "admin";
  const [query, setQuery] = useState("");
  const [classFilter, setClassFilter] = useState("all"); // all · none · class id
  const [catFilter, setCatFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [groupBy, setGroupBy] = useState<DirGroupBy>("class");
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const { data: all = [] } = useQuery({
    queryKey: ["students", query],
    queryFn: () => schoolApi.students({ q: query.trim() || undefined }),
  });
  const { data: classes = [] } = useQuery({
    queryKey: ["classes", yearId],
    queryFn: () => schoolApi.classes(yearId ?? undefined),
    enabled: !!yearId,
  });
  const { data: categories = [] } = useQuery({ queryKey: ["categories"], queryFn: schoolApi.categories });
  // Current support tier per student (SC-3) — a staff-only chip, never guardian-facing (P4).
  const { data: bandMap = {} } = useQuery({ queryKey: ["current-bands"], queryFn: schoolApi.currentBands });

  const classLabel = new Map(classes.map((c) => [c.id, c.name + (c.section ? `-${c.section}` : "")]));
  const catLabel = new Map(categories.map((c) => [c.id, c.name]));
  const students = all.filter((s) =>
    (classFilter === "all" ? true : classFilter === "none" ? !s.class_id : s.class_id === classFilter)
    && (catFilter === "all" ? true : s.category_id === catFilter)
    && (statusFilter === "all" ? true : s.status === statusFilter));

  // Group the filtered rows (Group by: Class is the default view).
  const keyOf = (s: StudentListItem) =>
    groupBy === "class" ? (s.class_id ? classLabel.get(s.class_id) ?? "?" : "Unassigned")
      : groupBy === "category" ? (s.category_id ? catLabel.get(s.category_id) ?? "—" : "No category")
        : groupBy === "status" ? s.status
          : groupBy === "band" ? (bandMap[s.id] ? `Band ${bandMap[s.id]}` : "No band")
            : "";
  const groups = new Map<string, StudentListItem[]>();
  for (const s of students) {
    const k = keyOf(s);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(s);
  }
  const ordered = [...groups.entries()].sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }));

  const renderTable = (rows: StudentListItem[]) => (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">Name</th>
            <th className="px-3 py-2 font-medium">Adm. no</th>
            <th className="px-3 py-2 font-medium">Roll</th>
            <th className="px-3 py-2 font-medium">Class</th>
            <th className="px-3 py-2 font-medium">Category</th>
            <th className="px-3 py-2 font-medium">Band</th>
            <th className="px-3 py-2 font-medium">Status</th>
            {canEdit ? <th className="px-3 py-2" /> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((s: StudentListItem) => (
            <tr
              key={s.id}
              onClick={() => router.push(`/students/${s.id}`)}
              className="cursor-pointer border-b border-border/60 bg-card last:border-0 hover:bg-muted/40"
            >
              <td className="px-3 py-2">
                <span className="flex items-center gap-2">
                  <Avatar name={s.full_name} />
                  <span className="font-medium">{s.full_name}</span>
                </span>
              </td>
              <td className="px-3 py-2 text-muted-foreground">{s.admission_no}</td>
              <td className="px-3 py-2 text-muted-foreground">{s.roll_no ?? "—"}</td>
              <td className="px-3 py-2">
                {s.class_id ? classLabel.get(s.class_id) ?? "?" : <Badge tone="warning">unassigned</Badge>}
              </td>
              <td className="px-3 py-2 text-muted-foreground">
                {s.category_id ? catLabel.get(s.category_id) ?? "—" : "—"}
              </td>
              <td className="px-3 py-2">
                {bandMap[s.id] ? <Badge tone={TIER_TONE[bandMap[s.id]]}>{bandMap[s.id]}</Badge> : <span className="text-muted-foreground">—</span>}
              </td>
              <td className="px-3 py-2">
                {s.status === "active" ? <span className="text-muted-foreground">active</span> : <Badge tone="neutral">{s.status}</Badge>}
              </td>
              {canEdit ? (
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    aria-label={`Edit ${s.full_name}`}
                    onClick={(e) => { e.stopPropagation(); setDetailId(s.id); }}
                    className="rounded-md p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Students ({students.length})</h1>
        {canEdit ? (
          <div className="flex gap-2">
            <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}><Upload className="h-4 w-4" /> Import</Button>
            <Button size="sm" onClick={() => setAddOpen(true)}><UserPlus className="h-4 w-4" /> Add</Button>
          </div>
        ) : null}
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <div className="relative min-w-48 flex-1 basis-48">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Search by name or admission no.…" value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        <Dropdown label="Group by" value={groupBy}
          options={[["class", "Class"], ["category", "Category"], ["status", "Status"], ["band", "Band"], ["none", "None"]]}
          onChange={(v) => setGroupBy(v as DirGroupBy)} />
        <Dropdown label="Class" value={classFilter}
          options={[["all", "All"], ...classes.map((c): [string, string] =>
            [c.id, c.name + (c.section ? `-${c.section}` : "")]), ["none", "Unassigned"]]}
          onChange={setClassFilter} />
        <Dropdown label="Category" value={catFilter}
          options={[["all", "All"], ...categories.map((c): [string, string] => [c.id, c.name])]}
          onChange={setCatFilter} />
        <Dropdown label="Status" value={statusFilter}
          options={[["all", "All"], ["active", "Active"], ["left", "Left"]]}
          onChange={setStatusFilter} />
      </div>
      {students.length === 0 ? (
        <EmptyState icon={Plus} title="No students match"
          body="Try clearing a filter — or add students to build the roster fees and academics both run on." />
      ) : groupBy === "none" ? (
        <div className="overflow-hidden rounded-xl border border-border shadow-sm">{renderTable(students)}</div>
      ) : (
        <div className="space-y-4">
          {ordered.map(([label, rows], gi) => (
            <div key={label} className="overflow-hidden rounded-xl border border-border shadow-sm">
              <div className="flex items-center gap-2 border-b border-border bg-card px-3 py-2">
                <span className="h-4 w-1 rounded-full" style={{ background: GROUP_COLORS[gi % GROUP_COLORS.length] }} />
                <p className="text-sm font-semibold">{label}</p>
                <span className="text-xs text-muted-foreground">{rows.length}</span>
              </div>
              {renderTable(rows)}
            </div>
          ))}
        </div>
      )}
      <AddStudentSheet open={addOpen} onOpenChange={setAddOpen} />
      <ImportSheet open={importOpen} onOpenChange={setImportOpen} />
      <StudentDetailSheet id={detailId} onClose={() => setDetailId(null)} canEdit={canEdit} />
    </div>
  );
}

export default function StudentsPage() {
  return (
    <AuthGuard>
      <StudentsInner />
    </AuthGuard>
  );
}
