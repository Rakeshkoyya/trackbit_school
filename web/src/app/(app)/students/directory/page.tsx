"use client";

/**
 * Students → Directory (founder, 2026-08-05) — the ADMINISTRATION roster.
 *
 * Who is on the books: name, admission number, class, category, status. It is
 * the office's table, admin-only to write, and it holds no mark, no attendance
 * figure and no band — those are Academics, one tab across, and a table that
 * carried both could serve neither.
 *
 * A row opens the child's record PAGE rather than a sheet. The record gets
 * corrected one fact at a time by someone with a parent on the phone; a sheet
 * with one "Save changes" over every field meant a half-typed name discarded a
 * fixed phone number, and it could not be linked to or left open.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Search, Upload, UserPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Dropdown } from "@/components/school/student-table";
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
  const [form, setForm] = useState({ admission_no: "", full_name: "", roll_no: "", class_id: "", category_id: "", date_of_birth: "" });
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
      date_of_birth: form.date_of_birth || null,
      guardians: g.name.trim() && g.phone.trim()
        ? [{ name: g.name.trim(), phone: g.phone.trim(), relation: g.relation.trim() || null, is_primary: true }]
        : [],
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success("Student added");
      setForm({ admission_no: "", full_name: "", roll_no: "", class_id: "", category_id: "", date_of_birth: "" });
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
        <div>
          <Label>Date of birth</Label>
          <Input type="date" value={form.date_of_birth} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} />
          <p className="mt-1 text-xs text-muted-foreground">The parent&apos;s login password — without it they can&apos;t sign in.</p>
        </div>
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
            {categories.length === 0 ? (
              // The real reason a student's category reads "—" is almost always
              // that the school has not defined any yet. Say that, and say where
              // to fix it, rather than rendering an empty dropdown (`D-129`).
              <p className="mt-1 text-xs text-muted-foreground">
                No categories yet — add them in{" "}
                <Link href="/setup/settings" className="underline">Settings</Link>.
              </p>
            ) : null}
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

/** Editing a child — identity and guardians both — moved to
 *  `/students/directory/[id]` (founder, 2026-08-05). It is a record corrected
 *  one fact at a time, which a single-save sheet could not do. */
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
      // D-13: an unreadable DOB is reported, never guessed — that parent
      // cannot log in until it's set by hand.
      if (res.unresolved?.length) {
        toast.warning(
          `${res.unresolved.length} date${res.unresolved.length === 1 ? "" : "s"} of birth `
          + `couldn't be read (${res.unresolved.slice(0, 3).map((u) => u.student).join(", ")}`
          + `${res.unresolved.length > 3 ? "…" : ""}) — those parents cannot log in until `
          + "it's fixed here.", { duration: 12000 });
      }
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
          <button
            onClick={() => schoolApi.downloadRosterTemplate().catch(() => toast.error("Could not download"))}
            className="text-sm font-medium text-primary hover:underline"
          >
            Download the blank template (.xlsx)
          </button>
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
// "band" left with the tier column (founder, 2026-08-05): a support tier is a
// teaching decision the programme owns, not an administration field, and it has
// its own area. Directory groups by the things the office files people under.
type DirGroupBy = "class" | "category" | "status" | "none";

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
      {/* `table-fixed` + colgroup: each class group is its own <table>, so auto
          layout sized every group's columns to its own content and "Adm. no"
          landed at a different x in 6-A than in 6-B. Same fix as Academics
          next door — the two halves are read one after the other. */}
      <table className="w-full min-w-[640px] table-fixed text-sm">
        <colgroup>
          <col className="w-[28%]" />
          <col className="w-[14%]" />
          <col className="w-[10%]" />
          <col className="w-[12%]" />
          <col className="w-[18%]" />
          <col className="w-[10%]" />
          <col className="w-[8%]" />
        </colgroup>
        <thead>
          <tr className="border-b border-border bg-muted/40 text-left text-xs text-muted-foreground">
            <th className="px-3 py-2 font-medium">Name</th>
            <th className="px-3 py-2 font-medium">Adm. no</th>
            <th className="px-3 py-2 font-medium">Roll</th>
            <th className="px-3 py-2 font-medium">Class</th>
            <th className="px-3 py-2 font-medium">Category</th>
            <th className="px-3 py-2 font-medium">Status</th>
            <th className="px-3 py-2" />
          </tr>
        </thead>
        <tbody>
          {rows.map((s: StudentListItem) => (
            <tr
              key={s.id}
              onClick={() => router.push(`/students/directory/${s.id}`)}
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
                {s.status === "active" ? <span className="text-muted-foreground">active</span> : <Badge tone="neutral">{s.status}</Badge>}
              </td>
              {/* The other half of this child. Directory renders no mark of its
                  own — this is the door to the record the school MAKES. */}
              <td className="px-3 py-2 text-right">
                <Link
                  href={`/students/${s.id}`}
                  onClick={(e) => e.stopPropagation()}
                  className="text-xs text-primary hover:underline"
                >
                  Report
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Directory ({students.length})</h1>
          <p className="text-sm text-muted-foreground">
            Who is on the books — the record the office keeps.
          </p>
        </div>
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
          options={[["class", "Class"], ["category", "Category"], ["status", "Status"], ["none", "None"]]}
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
    </div>
  );
}

export default function StudentsDirectoryPage() {
  return (
    <AuthGuard>
      <StudentsInner />
    </AuthGuard>
  );
}
