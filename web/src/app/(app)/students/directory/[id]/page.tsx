"use client";

/**
 * Students → Directory → one child: the ADMINISTRATION record (founder, 2026-08-05).
 *
 * This is the office's page, and it is deliberately the opposite of
 * `/students/[id]`: that one is a document you read (attendance, coverage,
 * marks, growth), this one is a form you correct. Name, date of birth, class,
 * category, status, and the guardians every outbound message in the product
 * keys on.
 *
 * **Edit in place, one section at a time.** The previous surface was a sheet
 * with a single "Save changes" over every field, which is wrong for a record
 * that gets corrected one fact at a time — a half-typed name would discard a
 * fixed phone number. Identity saves as a block; each guardian row saves on its
 * own tap, exactly as it did in the sheet (V1-13's rule, kept).
 *
 * What is NOT here, on purpose:
 *   · no marks, no attendance, no bands — that is Academics, and mixing them is
 *     how one table ended up serving neither;
 *   · no fees. Teachers never see fee data (§2), and this page is read by both
 *     roles even though only an admin may write it.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, BookOpen, Pencil, Phone, Plus, Trash2, X,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageLoading } from "@/components/ui/page-loading";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { Guardian, StudentDetail } from "@/lib/school-types";
import { cn } from "@/lib/utils";

function Card({ title, action, children }: {
  title: string; action?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      <header className="flex items-center justify-between gap-2 border-b border-border px-4 py-2.5">
        <h2 className="text-sm font-semibold">{title}</h2>
        {action}
      </header>
      <div className="p-4">{children}</div>
    </section>
  );
}

function Field({ label, value, warn }: { label: string; value: React.ReactNode; warn?: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 text-sm">{value}</dd>
      {warn ? <p className="mt-0.5 text-xs text-warning">{warn}</p> : null}
    </div>
  );
}

/** Identity + placement. Saves as one block because these fields are entered
 *  together at admission and corrected together when a child moves class. */
function IdentityBlock({ data, canEdit }: { data: StudentDetail; canEdit: boolean }) {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const [editing, setEditing] = useState(false);
  const { data: classes = [] } = useQuery({
    queryKey: ["classes", yearId],
    queryFn: () => schoolApi.classes(yearId ?? undefined), enabled: !!yearId && editing,
  });
  const { data: categories = [] } = useQuery({
    queryKey: ["categories"], queryFn: schoolApi.categories, enabled: editing,
  });
  const [form, setForm] = useState({
    full_name: data.full_name, roll_no: data.roll_no ?? "",
    class_id: data.class_id ?? "", category_id: data.category_id ?? "",
    date_of_birth: data.date_of_birth ?? "", status: data.status,
  });

  const save = useMutation({
    mutationFn: () => schoolApi.updateStudent(data.id, {
      full_name: form.full_name.trim(), roll_no: form.roll_no.trim() || null,
      class_id: form.class_id || null, category_id: form.category_id || null,
      date_of_birth: form.date_of_birth || null, status: form.status,
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["students"] });
      qc.invalidateQueries({ queryKey: ["student", data.id] });
      toast.success("Saved");
      setEditing(false);
    },
    onError: (e) => showApiError(e, "Could not save"),
  });

  if (!editing) {
    return (
      <Card title="Record" action={canEdit ? (
        <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
          <Pencil className="h-3.5 w-3.5" /> Edit
        </Button>
      ) : null}>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3">
          <Field label="Admission no." value={data.admission_no} />
          <Field label="Roll no." value={data.roll_no || "—"} />
          <Field label="Class" value={data.class_label
            || <Badge tone="warning">unassigned</Badge>} />
          <Field label="Category" value={data.category_name || "—"} />
          <Field
            label="Date of birth" value={data.date_of_birth || "—"}
            warn={data.date_of_birth ? undefined
              : "Missing — this parent cannot sign in to the portal."} />
          <Field label="Status" value={data.status === "active"
            ? <span className="text-muted-foreground">active</span>
            : <Badge tone="neutral">{data.status}</Badge>} />
        </dl>
      </Card>
    );
  }

  return (
    <Card title="Record" action={
      <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>
        <X className="h-3.5 w-3.5" /> Cancel
      </Button>
    }>
      <form className="space-y-3" onSubmit={(e) => {
        e.preventDefault(); if (form.full_name.trim()) save.mutate();
      }}>
        <div><Label>Full name</Label>
          <Input value={form.full_name} required
            onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></div>
        <div className="grid grid-cols-2 gap-2">
          <div><Label>Roll no.</Label>
            <Input value={form.roll_no}
              onChange={(e) => setForm({ ...form, roll_no: e.target.value })} /></div>
          <div>
            <Label>Date of birth</Label>
            <Input type="date" value={form.date_of_birth}
              onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} />
          </div>
        </div>
        {!form.date_of_birth ? (
          <p className="text-xs text-warning">
            The parent&apos;s portal password — without it they cannot sign in.
          </p>
        ) : null}
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label>Class</Label>
            <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              value={form.class_id}
              onChange={(e) => setForm({ ...form, class_id: e.target.value })}>
              <option value="">Unassigned</option>
              {classes.map((c) => (
                <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>
              ))}
            </select>
          </div>
          <div>
            <Label>Category</Label>
            <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
              value={form.category_id}
              onChange={(e) => setForm({ ...form, category_id: e.target.value })}>
              <option value="">—</option>
              {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
        </div>
        <div>
          <Label>Status</Label>
          <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value })}>
            <option value="active">active</option>
            <option value="left">left</option>
          </select>
        </div>
        <Button type="submit" className="w-full"
          disabled={save.isPending || !form.full_name.trim()}>
          {save.isPending ? "Saving…" : "Save changes"}
        </Button>
      </form>
    </Card>
  );
}

/**
 * Guardians — the rows every guardian-facing thing in the product keys on: the
 * absence alert, the homework note, the fee reminder, the portal's phone-OTP
 * recovery door, and the reach board that names families the school could not
 * deliver to.
 *
 * `notify_opt_out` is a toggle rather than a delete (V1-13): V1-11 counts an
 * opted-out family APART and keeps them off the list the office is told to
 * clear. Deleting the row would lose the fact that they asked, and the next
 * importer run would put them straight back.
 */
function GuardiansBlock({ studentId, guardians, canEdit }: {
  studentId: string; guardians: Guardian[]; canEdit: boolean;
}) {
  const qc = useQueryClient();
  const [g, setG] = useState({ name: "", phone: "", relation: "" });
  const refresh = () => qc.invalidateQueries({ queryKey: ["student", studentId] });

  const add = useMutation({
    mutationFn: () => schoolApi.addGuardian(studentId, {
      name: g.name.trim(), phone: g.phone.trim(),
      relation: g.relation.trim() || null, is_primary: guardians.length === 0,
    }),
    onSuccess: () => { refresh(); setG({ name: "", phone: "", relation: "" }); toast.success("Guardian added"); },
    onError: (e) => showApiError(e, "Could not add guardian"),
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { is_primary?: boolean; notify_opt_out?: boolean } }) =>
      schoolApi.updateGuardian(id, body),
    onSuccess: () => { refresh(); toast.success("Updated"); },
    onError: (e) => showApiError(e, "Could not update guardian"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteGuardian(id),
    onSuccess: () => { refresh(); toast.success("Guardian removed"); },
    onError: (e) => showApiError(e, "Could not remove guardian"),
  });

  return (
    <Card title="Guardians">
      {guardians.length === 0 ? (
        <p className="mb-3 text-sm text-warning">
          None on file — this family gets no attendance alert, no homework note and
          no fee reminder.
        </p>
      ) : (
        <ul className="mb-4 space-y-2.5">
          {guardians.map((gd) => (
            <li key={gd.id}
              className="flex flex-wrap items-center gap-x-2.5 gap-y-1 rounded-lg border border-border/70 px-3 py-2 text-sm">
              <span className="font-medium">{gd.name}</span>
              {gd.relation ? (
                <span className="text-xs text-muted-foreground">{gd.relation}</span>
              ) : null}
              <a href={`tel:${gd.phone}`}
                className="flex items-center gap-1 text-xs text-primary hover:underline">
                <Phone className="h-3 w-3" />{gd.phone}
              </a>
              {gd.is_primary ? (
                <Badge tone="primary" className="text-[10px]">primary</Badge>
              ) : canEdit ? (
                <button type="button" className="text-[11px] text-primary hover:underline"
                  onClick={() => update.mutate({ id: gd.id, body: { is_primary: true } })}>
                  make primary
                </button>
              ) : null}
              <button type="button" disabled={!canEdit}
                className={cn("text-[11px] disabled:cursor-default",
                  canEdit && "hover:underline",
                  gd.notify_opt_out ? "text-warning" : "text-muted-foreground")}
                title="A family that asked not to be messaged is counted apart, never chased."
                onClick={() => update.mutate({
                  id: gd.id, body: { notify_opt_out: !gd.notify_opt_out } })}>
                {gd.notify_opt_out ? "opted out of messages" : "receiving messages"}
              </button>
              {canEdit ? (
                <button type="button" className="ml-auto text-muted-foreground hover:text-danger"
                  onClick={() => remove.mutate(gd.id)} aria-label={`Remove ${gd.name}`}>
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      )}
      {canEdit ? (
        <div className="space-y-2 border-t border-border pt-3">
          <div className="grid grid-cols-2 gap-2">
            <Input placeholder="Name" value={g.name}
              onChange={(e) => setG({ ...g, name: e.target.value })} />
            <Input placeholder="Phone" value={g.phone}
              onChange={(e) => setG({ ...g, phone: e.target.value })} />
          </div>
          <div className="flex gap-2">
            <Input placeholder="Relation (Father/Mother)" value={g.relation}
              onChange={(e) => setG({ ...g, relation: e.target.value })} />
            <Button type="button" size="sm" variant="secondary"
              disabled={add.isPending || !g.name.trim() || g.phone.trim().length < 5}
              onClick={() => add.mutate()}>
              <Plus className="h-4 w-4" /> Add
            </Button>
          </div>
        </div>
      ) : null}
    </Card>
  );
}

function DirectoryRecord() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin";
  const { data, isLoading } = useQuery({
    queryKey: ["student", id], queryFn: () => schoolApi.student(id), enabled: !!id,
  });
  const remove = useMutation({
    mutationFn: () => schoolApi.deleteStudent(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["students"] });
      toast.success("Student removed");
      router.push("/students/directory");
    },
    onError: (e) => showApiError(e, "Could not remove"),
  });

  if (isLoading || !data) return <PageLoading />;

  return (
    <div className="space-y-4">
      <Link href="/students/directory"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Directory
      </Link>

      <div className="flex flex-wrap items-center gap-3">
        <Avatar name={data.full_name} />
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{data.full_name}</h1>
          <p className="text-sm text-muted-foreground">
            {data.admission_no}{data.class_label ? ` · ${data.class_label}` : ""}
          </p>
        </div>
        {/* The other half of this child, one tap away — the record the school
            MAKES about them. Directory never renders a mark of its own. */}
        <Link href={`/students/${data.id}`}
          className="ml-auto inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm font-medium hover:bg-muted">
          <BookOpen className="h-4 w-4" /> Academic report
        </Link>
      </div>

      <IdentityBlock data={data} canEdit={canEdit} />
      <GuardiansBlock studentId={data.id} guardians={data.guardians} canEdit={canEdit} />

      {canEdit ? (
        <Button variant="outline" className="text-danger"
          onClick={() => remove.mutate()}>
          <Trash2 className="h-4 w-4" /> Remove student
        </Button>
      ) : null}
    </div>
  );
}

export default function StudentDirectoryRecordPage() {
  return (
    <AuthGuard>
      <DirectoryRecord />
    </AuthGuard>
  );
}
