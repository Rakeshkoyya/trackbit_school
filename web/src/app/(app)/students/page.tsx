"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Trash2, Upload, UserPlus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
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

function StudentDetailSheet({ id, onClose, canEdit }: { id: string | null; onClose: () => void; canEdit: boolean }) {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["student", id], queryFn: () => schoolApi.student(id!), enabled: !!id });
  const remove = useMutation({
    mutationFn: () => schoolApi.deleteStudent(id!),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["students"] }); toast.success("Student removed"); onClose(); },
    onError: (e) => showApiError(e, "Could not remove"),
  });
  return (
    <Sheet open={!!id} onOpenChange={(v) => { if (!v) onClose(); }} title={data?.full_name ?? "Student"}>
      {data ? (
        <div className="space-y-4 text-sm">
          <div className="flex flex-wrap gap-x-6 gap-y-1">
            <p><span className="text-muted-foreground">Admission</span> {data.admission_no}</p>
            {data.roll_no ? <p><span className="text-muted-foreground">Roll</span> {data.roll_no}</p> : null}
            <p><span className="text-muted-foreground">Class</span> {data.class_label ?? "—"}</p>
            <p><span className="text-muted-foreground">Category</span> {data.category_name ?? "—"}</p>
            <p><Badge tone={data.status === "active" ? "primary" : "neutral"}>{data.status}</Badge></p>
          </div>
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

function StudentsInner() {
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin" || me?.org_role === "coordinator";
  const [query, setQuery] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const { data: students = [] } = useQuery({
    queryKey: ["students", query],
    queryFn: () => schoolApi.students({ q: query.trim() || undefined }),
  });

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
      <div className="relative mb-4">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input className="pl-9" placeholder="Search by name or admission no.…" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      {students.length === 0 ? (
        <EmptyState icon={Plus} title="No students yet" body="Add students to build the roster fees and academics both run on." />
      ) : (
        <div className="space-y-2">
          {students.map((s: StudentListItem) => (
            <button key={s.id} onClick={() => setDetailId(s.id)} className="flex w-full items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 text-left hover:bg-muted/40">
              <Avatar name={s.full_name} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{s.full_name}</p>
                <p className="truncate text-xs text-muted-foreground">
                  Adm. {s.admission_no}{s.roll_no ? ` · Roll ${s.roll_no}` : ""}
                </p>
              </div>
              {s.status !== "active" ? <Badge tone="neutral">{s.status}</Badge> : null}
            </button>
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
