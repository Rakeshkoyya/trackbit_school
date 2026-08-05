"use client";

// The staff directory (founder, 2026-08-05) — who works here, in one table.
//
// Setup → Members is the ACCOUNT screen: invite state, reset a password, remove
// somebody. It cannot answer the questions an admin actually asks about staff —
// who teaches 6-A, who is its class teacher, who is carrying nine class-subjects
// and who is carrying two — because none of that lives on `memberships`.
//
// THE ONE RULE WORTH RESTATING WHERE THE PIXELS ARE: **"Class teacher" is not a
// role.** It is `school_classes.class_teacher_member_id`, and picking it in this
// dropdown opens a class picker and writes the CLASS. The stored role stays
// `admin | teacher` — the two-value column every guard in the app is built on.
// A third role value would put the same fact in two places, and they would
// disagree the first time a class was reassigned.
//
// Table language is the task module's, deliberately: colour-barred group
// headers, uppercase column heads over CSS-grid rows, `Popover` for pickers.
// The difference kept on purpose is that a row here OPENS a person rather than
// editing in place — a staff row is a file you go into, not a field you tweak.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, Search, ShieldCheck, UserCog, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { Popover } from "@/components/ui/popover";
import { showApiError } from "@/lib/errors";
import { groupColor } from "@/lib/format";
import { schoolApi } from "@/lib/school-api";
import type { ClassRef, StaffDirectory, StaffRoleKey, StaffRow } from "@/lib/school-types";
import { cn } from "@/lib/utils";

import { Dropdown } from "@/components/school/student-table";

type GroupBy = "role" | "class" | "none";

const ROLE_META: Record<StaffRoleKey, { label: string; hint: string }> = {
  admin: { label: "Admin", hint: "Runs the school — setup, fees, dashboard, staff" },
  class_teacher: {
    label: "Class teacher",
    hint: "A teacher who also owns a homeroom. Pick the class next.",
  },
  teacher: { label: "Teacher", hint: "Teaches subjects; no homeroom" },
};

const ROLE_TONE: Record<StaffRoleKey, "neutral" | "success" | "warning" | "danger"> = {
  admin: "warning",
  class_teacher: "success",
  teacher: "neutral",
};

const COLS = "minmax(0,2.2fr) 11.5rem minmax(0,1.4fr) 6.5rem";

function timeAgo(iso: string | null): string {
  if (!iso) return "never";
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  if (m < 1440) return `${Math.floor(m / 60)}h ago`;
  return `${Math.floor(m / 1440)}d ago`;
}

/**
 * The Role cell. Three options, and one of them asks a second question.
 *
 * Picking "Class teacher" does NOT save on the tap — it swaps the popover for a
 * class list, because "class teacher" without a class is not a state the school
 * can be in. Picking a class the popover shows as already owned still saves: a
 * homeroom has one owner and handing it over is a normal Monday.
 */
function RoleCell({ row, classes, owners, onSave, saving }: {
  row: StaffRow;
  classes: ClassRef[];
  /** class_id → the name currently holding it, for the "currently X" hint. */
  owners: Record<string, string>;
  onSave: (body: { org_role?: "admin" | "teacher"; class_teacher_of?: string[] }) => void;
  saving: boolean;
}) {
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [picking, setPicking] = useState(false);

  const close = () => {
    setRect(null);
    setPicking(false);
  };

  return (
    <>
      <button type="button" disabled={saving}
        onClick={(e) => {
          e.stopPropagation();
          setRect(e.currentTarget.getBoundingClientRect());
          setPicking(false);
        }}
        className="inline-flex max-w-full items-center gap-1 rounded-md px-1.5 py-1 text-left text-sm hover:bg-muted disabled:opacity-50">
        <Badge tone={ROLE_TONE[row.role_key]}>{ROLE_META[row.role_key].label}</Badge>
        {row.class_teacher_of.length ? (
          <span className="truncate text-xs text-muted-foreground">
            {row.class_teacher_of.map((c) => c.class_label).join(", ")}
          </span>
        ) : null}
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      </button>

      <Popover open={rect != null} rect={rect} onClose={close} width={260}>
        {!picking ? (
          <div onClick={(e) => e.stopPropagation()}>
            {(Object.keys(ROLE_META) as StaffRoleKey[]).map((key) => (
              <button key={key} type="button"
                onClick={() => {
                  if (key === "class_teacher") {
                    setPicking(true);
                    return;
                  }
                  // Moving OFF class teacher hands the homeroom back — the class
                  // is left with nobody, which is the state the admin must see,
                  // rather than a person who no longer holds the role still
                  // being named on the class.
                  close();
                  onSave({
                    org_role: key,
                    ...(row.class_teacher_of.length ? { class_teacher_of: [] } : {}),
                  });
                }}
                className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left hover:bg-muted">
                <span className="mt-[3px] h-3.5 w-3.5 shrink-0">
                  {row.role_key === key ? <Check className="h-3.5 w-3.5 text-primary" /> : null}
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium">{ROLE_META[key].label}</span>
                  <span className="block text-[11px] leading-snug text-muted-foreground">
                    {ROLE_META[key].hint}
                  </span>
                </span>
              </button>
            ))}
          </div>
        ) : (
          <div onClick={(e) => e.stopPropagation()}>
            <p className="px-2 py-1 text-[11px] uppercase tracking-wide text-muted-foreground">
              Class teacher of
            </p>
            {classes.length === 0 ? (
              <p className="px-2 py-2 text-xs text-muted-foreground">
                No classes in this year yet — add them in Setup → Academics.
              </p>
            ) : null}
            <div className="max-h-64 overflow-y-auto">
              {classes.map((c) => {
                const mine = row.class_teacher_of.some((x) => x.class_id === c.class_id);
                const held = owners[c.class_id];
                return (
                  <button key={c.class_id} type="button"
                    onClick={() => {
                      close();
                      // Full replace, and one homeroom at a time from this cell.
                      // Multiple homerooms are legitimate but rare, and they are
                      // edited on the person's own page where there is room to
                      // show what is being taken away.
                      onSave({
                        org_role: row.org_role === "admin" ? undefined : "teacher",
                        class_teacher_of: mine ? [] : [c.class_id],
                      });
                    }}
                    className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left hover:bg-muted">
                    <span className="h-3.5 w-3.5 shrink-0">
                      {mine ? <Check className="h-3.5 w-3.5 text-primary" /> : null}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm">{c.class_label}</span>
                      {held && !mine ? (
                        <span className="block text-[11px] text-muted-foreground">
                          currently {held} — this hands it over
                        </span>
                      ) : null}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </Popover>
    </>
  );
}

function Head() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: COLS }}
      className="border-b border-border bg-muted/20 px-3 py-1.5 font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
      <span>Name</span>
      <span>Role</span>
      <span>Classes &amp; subjects</span>
      <span className="text-right">Last active</span>
    </div>
  );
}

export function StaffDirectoryTable() {
  const qc = useQueryClient();
  const router = useRouter();
  const { data, isLoading } = useQuery<StaffDirectory>({
    queryKey: ["staff", "directory"],
    queryFn: schoolApi.staffDirectory,
  });

  const [q, setQ] = useState("");
  const [grouping, setGrouping] = useState<GroupBy>("role");
  const [roleFilter, setRoleFilter] = useState<string>("all");
  const [classFilter, setClassFilter] = useState<string>("all");
  const [savingId, setSavingId] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: ({ memberId, body }: {
      memberId: string;
      body: { org_role?: "admin" | "teacher"; class_teacher_of?: string[] };
    }) => schoolApi.updateStaff(memberId, body),
    onMutate: ({ memberId }) => setSavingId(memberId),
    onSettled: () => setSavingId(null),
    onSuccess: (res) => {
      toast.success(`${res.row.name} — ${res.row.role_label}`);
      qc.invalidateQueries({ queryKey: ["staff", "directory"] });
      // The nav's My Class item and every homeroom-scoped read key off the same
      // column, so they are stale the moment this lands.
      qc.invalidateQueries({ queryKey: ["me"] });
      qc.invalidateQueries({ queryKey: ["my-classes"] });
      qc.invalidateQueries({ queryKey: ["classes"] });
    },
    onError: (e) => showApiError(e, "Could not save that"),
  });

  if (isLoading) return <PageLoading label="Loading staff…" />;
  if (!data) return null;
  if (!data.rows.length) {
    return (
      <EmptyState icon={Users} title="No staff yet"
        body="Add teachers and admins in Setup → Members; they appear here with the classes they take." />
    );
  }

  const owners: Record<string, string> = {};
  for (const r of data.rows) {
    for (const c of r.class_teacher_of) owners[c.class_id] = r.name;
  }

  const needle = q.trim().toLowerCase();
  const visible = data.rows.filter((r) => {
    if (roleFilter !== "all" && r.role_key !== roleFilter) return false;
    if (classFilter !== "all" && !r.classes.some((c) => c.class_id === classFilter)) return false;
    if (!needle) return true;
    return (
      r.name.toLowerCase().includes(needle)
      || (r.email ?? "").toLowerCase().includes(needle)
      || (r.username ?? "").toLowerCase().includes(needle)
      || (r.phone ?? "").includes(needle)
      || r.classes.some((c) => c.class_label.toLowerCase().includes(needle))
      || r.subjects.some((s) => s.subject_name.toLowerCase().includes(needle))
    );
  });

  // Grouped by class, one person appears under EVERY class they are in front of
  // — that is what the grouping is for, and de-duplicating to a "primary" class
  // would silently hide half of what a teacher carries.
  const groups = new Map<string, StaffRow[]>();
  for (const r of visible) {
    if (grouping === "none") {
      if (!groups.has("")) groups.set("", []);
      groups.get("")!.push(r);
    } else if (grouping === "role") {
      const k = ROLE_META[r.role_key].label;
      if (!groups.has(k)) groups.set(k, []);
      groups.get(k)!.push(r);
    } else {
      const keys = r.classes.length ? r.classes.map((c) => c.class_label) : ["No class"];
      for (const k of keys) {
        if (!groups.has(k)) groups.set(k, []);
        groups.get(k)!.push(r);
      }
    }
  }
  const ordered = [...groups.entries()].sort(([a], [b]) =>
    a.localeCompare(b, undefined, { numeric: true }));

  return (
    <div>
      {/* The gap first, because it is the only thing here that is WRONG rather
          than merely informative: a class with no class teacher has nobody
          taking its register at period one. */}
      {data.classes_without_teacher.length ? (
        <div className="mb-3 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-warning/40 bg-warning/5 px-3 py-2 text-sm">
          <UserCog className="h-4 w-4 shrink-0 text-warning" />
          <span>
            <span className="font-medium">
              {data.classes_without_teacher.length}{" "}
              {data.classes_without_teacher.length === 1 ? "class has" : "classes have"} no
              class teacher
            </span>{" "}
            <span className="text-muted-foreground">
              — {data.classes_without_teacher.map((c) => c.class_label).join(", ")}. Set one
              from the Role column.
            </span>
          </span>
        </div>
      ) : null}

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-0 flex-1 basis-40">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="h-9 pl-8" placeholder="Search name, class, subject…"
            value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <Dropdown label="Group by" value={grouping}
          options={[["role", "Role"], ["class", "Class"], ["none", "None"]]}
          onChange={(v) => setGrouping(v as GroupBy)} />
        <Dropdown label="Role" value={roleFilter}
          options={[["all", `All (${data.total})`],
            ["admin", `Admins (${data.admins})`],
            ["class_teacher", `Class teachers (${data.class_teachers})`],
            ["teacher", "Teachers"]]}
          onChange={setRoleFilter} />
        <Dropdown label="Class" value={classFilter}
          options={[["all", "All classes"] as [string, string],
            ...data.classes.map((c) => [c.class_id, c.class_label] as [string, string])]}
          onChange={setClassFilter} />
      </div>

      {visible.length === 0 ? (
        <p className="rounded-xl border border-border bg-card px-4 py-6 text-center text-sm text-muted-foreground">
          Nobody matches.
        </p>
      ) : (
        <div className="space-y-4">
          {ordered.map(([label, rows]) => (
            <div key={label || "all"}
              className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
              {label ? (
                <div className="flex items-center gap-2 border-b border-border px-3 py-2">
                  <span className="h-3.5 w-1 rounded-full"
                    style={{ background: groupColor(label) }} />
                  <span className="text-sm font-semibold">{label}</span>
                  <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                    {rows.length}
                  </span>
                </div>
              ) : null}
              <Head />
              {rows.map((r) => (
                <div key={`${label}-${r.member_id}`}
                  onClick={() => router.push(`/staff/member/${r.member_id}`)}
                  style={{ display: "grid", gridTemplateColumns: COLS, alignItems: "center" }}
                  className="cursor-pointer border-b border-border/60 px-3 py-2 last:border-b-0 hover:bg-muted/40">
                  <span className="flex min-w-0 items-center gap-2">
                    <Avatar name={r.name} />
                    <span className="min-w-0">
                      <span className="flex items-center gap-1.5">
                        <span className="truncate text-sm font-medium">{r.name}</span>
                        {r.org_role === "admin" ? (
                          <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-warning" />
                        ) : null}
                        {r.pending ? <Badge tone="neutral">invited</Badge> : null}
                      </span>
                      <span className="block truncate text-[11px] text-muted-foreground">
                        {r.email ?? r.username ?? r.phone ?? "no contact on file"}
                      </span>
                    </span>
                  </span>

                  <span onClick={(e) => e.stopPropagation()}>
                    <RoleCell row={r} classes={data.classes} owners={owners}
                      saving={savingId === r.member_id}
                      onSave={(body) => save.mutate({ memberId: r.member_id, body })} />
                  </span>

                  <span className="min-w-0 pr-2 text-[12px] leading-snug">
                    {r.subject_count ? (
                      <>
                        <span className="block truncate">
                          {r.subjects.map((s) => `${s.class_label} ${s.subject_name}`).join(" · ")}
                        </span>
                        <span className="block font-mono text-[10px] text-muted-foreground">
                          {r.subject_count} {r.subject_count === 1 ? "subject" : "subjects"}
                          {r.periods_per_week ? ` · ${r.periods_per_week} periods/week` : ""}
                        </span>
                      </>
                    ) : (
                      // Never a zero dressed as a failure — a warden or an office
                      // admin teaches nothing and that is the job.
                      <span className="text-muted-foreground">not teaching a subject</span>
                    )}
                  </span>

                  <span className={cn("text-right font-mono text-[11px] tabular-nums",
                    r.last_active_at ? "text-muted-foreground" : "text-muted-foreground/60")}>
                    {timeAgo(r.last_active_at)}
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
