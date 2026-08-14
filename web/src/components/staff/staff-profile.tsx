"use client";

// One member of staff's FILE (founder, 2026-08-05) — the editable half of the
// page whose other half is the V1-16 record.
//
// The split is deliberate and is the same one the rest of the app makes: this
// block is the person's *establishment* — name, contact, role, homeroom, what
// they teach. `StaffRecordView` below it is their *time*, and it is a record
// rather than an appraisal (`D-25`/`S-67`): no score, no rank, no path to pay.
// Keeping them apart is what stops an edit form growing a "performance" section.
//
// Read by both roles; the SERVER decides what that means. A teacher opening her
// own file gets `can_edit: false` and sees the same facts with no inputs — a
// person whose file is kept must be able to read it, and nobody else's.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Pencil, X } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { StaffDetail, StaffRoleKey, StaffUpdateIn } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const ROLE_LABEL: Record<StaffRoleKey, string> = {
  admin: "Admin",
  class_teacher: "Class teacher",
  teacher: "Teacher",
};

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <span className="block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </span>
      <span className="mt-0.5 block text-sm">{value}</span>
    </div>
  );
}

export function StaffProfileCard({ memberId }: { memberId: string }) {
  const qc = useQueryClient();
  const { data } = useQuery<StaffDetail>({
    queryKey: ["staff", "detail", memberId],
    queryFn: () => schoolApi.staffDetail(memberId),
  });
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<StaffUpdateIn>({});
  const [homerooms, setHomerooms] = useState<string[] | null>(null);

  const save = useMutation({
    mutationFn: (body: StaffUpdateIn) => schoolApi.updateStaff(memberId, body),
    onSuccess: (res) => {
      toast.success("Saved");
      setEditing(false);
      setForm({});
      setHomerooms(null);
      qc.setQueryData(["staff", "detail", memberId], res);
      qc.invalidateQueries({ queryKey: ["staff", "directory"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["my-classes"] });
    },
    onError: (e) => showApiError(e, "Could not save"),
  });

  if (!data) return null;
  const { row, classes, can_edit: canEdit, is_last_admin: isLastAdmin } = data;

  const start = () => {
    setForm({
      name: row.name,
      email: row.email ?? "",
      phone: row.phone ?? "",
      date_of_birth: row.date_of_birth ?? "",
      org_role: row.org_role,
    });
    setHomerooms(row.class_teacher_of.map((c) => c.class_id));
    setEditing(true);
  };

  const submit = () => {
    const body: StaffUpdateIn = { name: form.name?.trim() || row.name };
    // An empty box means "clear it", which needs its own flag — an absent field
    // means "leave it alone", and the two must not be the same wire value.
    if ((form.email ?? "") !== (row.email ?? "")) {
      if (form.email) body.email = form.email;
      else body.clear_email = true;
    }
    if ((form.phone ?? "") !== (row.phone ?? "")) {
      if (form.phone) body.phone = form.phone;
      else body.clear_phone = true;
    }
    if ((form.date_of_birth ?? "") !== (row.date_of_birth ?? "")) {
      if (form.date_of_birth) body.date_of_birth = form.date_of_birth;
      else body.clear_date_of_birth = true;
    }
    if (form.org_role && form.org_role !== row.org_role) body.org_role = form.org_role;
    if (homerooms) {
      const before = [...row.class_teacher_of.map((c) => c.class_id)].sort().join();
      if ([...homerooms].sort().join() !== before) body.class_teacher_of = homerooms;
    }
    save.mutate(body);
  };

  return (
    <section className="mb-5 overflow-hidden rounded-xl border border-border bg-card">
      <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2.5">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          Staff file
        </span>
        <Badge tone={row.role_key === "admin" ? "warning"
          : row.role_key === "class_teacher" ? "success" : "neutral"}>
          {row.role_label}
        </Badge>
        {canEdit ? (
          <span className="ml-auto flex items-center gap-2">
            {editing ? (
              <>
                <Button size="sm" variant="outline" onClick={() => { setEditing(false); setHomerooms(null); }}>
                  <X className="h-3.5 w-3.5" /> Cancel
                </Button>
                <Button size="sm" onClick={submit} disabled={save.isPending}>
                  <Check className="h-3.5 w-3.5" /> {save.isPending ? "Saving…" : "Save"}
                </Button>
              </>
            ) : (
              <Button size="sm" variant="outline" onClick={start}>
                <Pencil className="h-3.5 w-3.5" /> Edit
              </Button>
            )}
          </span>
        ) : null}
      </header>

      {!editing ? (
        <div className="grid gap-4 px-4 py-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label="Name" value={row.name} />
          <Field label="Email" value={row.email ?? <span className="text-muted-foreground">—</span>} />
          <Field label="Phone" value={row.phone
            ? <a href={`tel:${row.phone}`} className="text-primary hover:underline">{row.phone}</a>
            : <span className="text-muted-foreground">—</span>} />
          <Field label="Username" value={row.username ?? <span className="text-muted-foreground">—</span>} />
          <Field label="Date of birth" value={row.date_of_birth
            ? new Date(`${row.date_of_birth}T00:00:00`).toLocaleDateString(undefined,
              { day: "numeric", month: "long", year: "numeric" })
            : <span className="text-muted-foreground">not on file</span>} />
          <Field label="Class teacher of" value={row.class_teacher_of.length
            ? row.class_teacher_of.map((c) => c.class_label).join(", ")
            : <span className="text-muted-foreground">no homeroom</span>} />
          <Field label="Teaching load" value={row.subject_count
            ? `${row.subject_count} ${row.subject_count === 1 ? "subject" : "subjects"}`
              + (row.periods_per_week ? ` · ${row.periods_per_week} periods/week` : "")
            : <span className="text-muted-foreground">not teaching a subject</span>} />
          <Field label="Signed in" value={row.last_active_at
            ? new Date(row.last_active_at).toLocaleString()
            : <span className="text-muted-foreground">never</span>} />
        </div>
      ) : (
        <div className="space-y-4 px-4 py-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div>
              <Label htmlFor="sf-name">Name</Label>
              <Input id="sf-name" value={form.name ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="sf-email">Email</Label>
              <Input id="sf-email" type="email" value={form.email ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, email: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="sf-phone">Phone</Label>
              <Input id="sf-phone" value={form.phone ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
            </div>
            <div>
              <Label htmlFor="sf-dob">Date of birth</Label>
              <Input id="sf-dob" type="date" value={form.date_of_birth ?? ""}
                onChange={(e) => setForm((f) => ({ ...f, date_of_birth: e.target.value }))} />
            </div>
          </div>

          <div>
            <Label>Role</Label>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {(["admin", "teacher"] as const).map((r) => {
                const blocked = r === "teacher" && isLastAdmin;
                return (
                  <button key={r} type="button" disabled={blocked}
                    onClick={() => setForm((f) => ({ ...f, org_role: r }))}
                    className={cn(
                      "rounded-full border px-3 py-1 text-sm disabled:cursor-not-allowed disabled:opacity-50",
                      form.org_role === r ? "border-primary bg-primary/10 font-medium" : "border-border")}>
                    {ROLE_LABEL[r]}
                  </button>
                );
              })}
            </div>
            {/* Said before the tap, not after it. The refusal itself lives in
                `MemberService.change_role`; this is only the warning. */}
            {isLastAdmin ? (
              <p className="mt-1 text-[11px] text-muted-foreground">
                The last admin can&rsquo;t be moved to teacher — promote somebody else first.
              </p>
            ) : null}
          </div>

          <div>
            <Label>Class teacher of</Label>
            <p className="mb-1.5 text-[11px] text-muted-foreground">
              A homeroom has one owner. Picking a class another teacher holds hands it over.
            </p>
            <div className="flex flex-wrap gap-1.5">
              {classes.length === 0 ? (
                <span className="text-sm text-muted-foreground">
                  No classes in this year yet.
                </span>
              ) : null}
              {classes.map((c) => {
                const on = (homerooms ?? []).includes(c.class_id);
                return (
                  <button key={c.class_id} type="button"
                    onClick={() => setHomerooms((prev) => {
                      const cur = prev ?? [];
                      return on ? cur.filter((x) => x !== c.class_id) : [...cur, c.class_id];
                    })}
                    className={cn("rounded-full border px-3 py-1 text-sm",
                      on ? "border-primary bg-primary/10 font-medium" : "border-border")}>
                    {c.class_label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}

      <TeachesSection memberId={memberId} row={row} canEdit={data.can_edit} />
    </section>
  );
}

/** What this member teaches — and, for an admin, the one control that was
 *  missing (`D-130`).
 *
 *  The founder's sentence: *"I want to remove EVS of 5 class currently mapped to
 *  Aarti madam and map it to another teacher"*. Both the API and a dropdown for
 *  it already existed, on Setup → class — behind `require_operator`, which
 *  freezes at handover. So on a live school the control was there and greyed
 *  out, in a place you had to already know about. The staff file is where
 *  somebody actually looks for it, because the question starts with the person.
 *
 *  Adding or removing a subject from a class stays on Setup and stays frozen:
 *  that is curriculum. Handing one to a colleague is a Tuesday. */
function TeachesSection({ memberId, row, canEdit }: {
  memberId: string; row: StaffDetail["row"]; canEdit: boolean;
}) {
  const qc = useQueryClient();
  const [adding, setAdding] = useState(false);

  // Only fetched when an admin can act on it — a teacher reading her own file
  // has no use for the whole school's roster.
  const { data: directory } = useQuery({
    queryKey: ["staff", "directory"],
    queryFn: () => schoolApi.staffDirectory(),
    enabled: canEdit,
  });
  const { data: allCs = [] } = useQuery({
    queryKey: ["class-subjects", "all"],
    queryFn: () => schoolApi.allClassSubjects(),
    enabled: canEdit && adding,
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["staff"] });
    qc.invalidateQueries({ queryKey: ["class-subjects"] });
    // Who teaches what decides My Day, the register and the clash validator, so
    // everything downstream has to be re-read, not just this card.
    qc.invalidateQueries({ queryKey: ["timetable-clashes"] });
    qc.invalidateQueries({ queryKey: ["my-day"] });
  };
  const move = useMutation({
    mutationFn: ({ csId, to }: { csId: string; to: string | null }) =>
      schoolApi.setClassSubjectTeacher(csId, to),
    onSuccess: (_res, v) => {
      invalidate();
      toast.success(v.to
        ? "Subject moved to the new teacher"
        : "Subject left unassigned");
    },
    onError: (e) => showApiError(e, "Could not change the teacher"),
  });

  // `core/staff.py::not_operator()` already keeps the platform operator out of
  // the roster read, so this list is the school's own people.
  const teachers = (directory?.rows ?? []).filter((t) => t.status === "active");
  const mine = new Set(row.subjects.map((s) => s.class_subject_id));
  const spare = allCs.filter((cs) => !mine.has(cs.id));

  if (!row.subjects.length && !canEdit) return null;

  return (
    <div className="border-t border-border px-4 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
          Teaches
        </span>
        {canEdit ? (
          <Button size="sm" variant="ghost" onClick={() => setAdding((v) => !v)}>
            {adding ? "Cancel" : "+ Add a subject"}
          </Button>
        ) : null}
      </div>

      {!canEdit ? (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {row.subjects.map((s) => (
            <Link key={s.class_subject_id}
              href={`/plan/syllabus?class_subject=${s.class_subject_id}`}
              className="rounded-full border border-border px-2.5 py-1 text-xs hover:bg-muted">
              {s.class_label} {s.subject_name}
              {s.periods_per_week ? (
                <span className="ml-1 font-mono text-[10px] text-muted-foreground">
                  {s.periods_per_week}/wk
                </span>
              ) : null}
            </Link>
          ))}
        </div>
      ) : (
        <div className="mt-1.5 space-y-1">
          {row.subjects.length === 0 && !adding ? (
            <p className="text-sm text-muted-foreground">
              No subjects assigned yet.
            </p>
          ) : null}
          {row.subjects.map((s) => (
            <div key={s.class_subject_id}
              className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-1.5">
              <Link href={`/plan/syllabus?class_subject=${s.class_subject_id}`}
                className="min-w-0 flex-1 truncate text-sm hover:underline">
                <span className="font-medium">{s.class_label}</span>{" "}
                {s.subject_name}
                {s.periods_per_week ? (
                  <span className="ml-1 font-mono text-[10px] text-muted-foreground">
                    {s.periods_per_week}/wk
                  </span>
                ) : null}
              </Link>
              {/* Changing the name here MOVES the subject — she loses it and the
                  chosen colleague gains it. One control, said plainly. */}
              <select
                aria-label={`Who teaches ${s.class_label} ${s.subject_name}`}
                className="h-8 max-w-44 rounded-md border border-border bg-background px-2 text-sm"
                value={memberId}
                disabled={move.isPending}
                onChange={(e) => move.mutate({
                  csId: s.class_subject_id, to: e.target.value || null })}>
                {teachers.map((t) => (
                  <option key={t.member_id} value={t.member_id}>{t.name}</option>
                ))}
                <option value="">Nobody yet</option>
              </select>
            </div>
          ))}

          {adding ? (
            <div className="rounded-lg border border-dashed border-border px-2.5 py-2">
              <p className="mb-1 text-xs text-muted-foreground">
                Pick a class-subject to give her. One with a teacher already moves
                across — nothing is taught twice.
              </p>
              <select
                aria-label="Add a subject for this teacher"
                className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
                value=""
                disabled={move.isPending}
                onChange={(e) => {
                  if (!e.target.value) return;
                  move.mutate({ csId: e.target.value, to: memberId });
                  setAdding(false);
                }}>
                <option value="">Choose a class and subject…</option>
                {spare.map((cs) => (
                  <option key={cs.id} value={cs.id}>
                    {cs.class_label ?? ""} {cs.subject_name}
                    {cs.teacher_member_id ? " — currently assigned" : " — unassigned"}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
