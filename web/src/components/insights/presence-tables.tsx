"use client";

// V1-14 — the attendance tab's *work* half: three tables of people, each row
// carrying what somebody needs before they pick up a phone or move a period.
//
// **The table language is the task module's** (`boards/board-table.tsx`), because
// an admin who has learned one table in this product should not have to learn a
// second. What is borrowed: the card shell, the group header with its colour bar
// and count, the uppercase column head over CSS-grid rows (never a `<table>`, so
// columns stay aligned across groups), the row hover, and the portal `Popover`
// for pickers. What is different, and why: these rows END in actions rather than
// inline edits — a task row is a thing you change, an absence row is a thing you
// *respond to* — so the last column is a fixed action rail and the row itself is
// not a click target.
//
// Colour is a rendering of a server-computed status (`S-22`), never a decision
// made here: `tone` on a profile is already `D-86`'s red/amber, and a long
// absence somebody has *explained* is never red however long it runs.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRightLeft, CalendarClock, Check, MessageSquare, NotebookPen, Search,
  UserPlus, UserX,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { UpgradeGate } from "@/components/plan/upgrade";
import { Button } from "@/components/ui/button";
import { FEATURES } from "@/lib/features";
import { Input } from "@/components/ui/input";
import { Popover } from "@/components/ui/popover";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import type {
  AbsenceProfile, AdminWorkRow, PresenceRow, StaffAbsentee,
} from "@/lib/insights-types";
import { cn } from "@/lib/utils";

import { Empty, Fraction, StateChip, TONE_BADGE, type Tone } from "./shared";

// ── the shared table furniture ───────────────────────────────────────────────

const ROW_TONE: Record<Tone, string> = {
  red: "bg-danger/[0.055]",
  amber: "bg-warning-soft/25",
  green: "",
  neutral: "",
};

const BAR: Record<Tone, string> = {
  red: "var(--chart-red)",
  amber: "var(--chart-amber)",
  green: "var(--chart-green)",
  neutral: "var(--color-muted-foreground)",
};

function gridStyle(cols: string): React.CSSProperties {
  return { display: "grid", gridTemplateColumns: cols, alignItems: "center" };
}

/** The card every one of these tables sits in — one shell, three tables. */
function TableCard({ children }: { children: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card shadow-sm">
      {children}
    </div>
  );
}

/** A group of rows, keyed at its left edge by a colour bar and counted — the
 *  board's group header, which is where an admin already looks for a count. */
function GroupHeader({
  label, count, tone = "neutral",
}: {
  label: string;
  count: number;
  tone?: Tone;
}) {
  return (
    <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-3 py-2 text-sm font-semibold"
      style={{ borderLeft: `3px solid ${BAR[tone]}` }}>
      <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: BAR[tone] }} />
      {label}
      <span className="font-mono text-xs font-normal tabular-nums text-muted-foreground">
        {count}
      </span>
    </div>
  );
}

function HeadRow({ cols, labels }: { cols: string; labels: string[] }) {
  return (
    <div style={gridStyle(cols)}
      className="border-b border-border bg-muted/20 px-3 py-2 font-mono text-[10px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
      {labels.map((l) => (
        <span key={l} className={l === "Act" ? "text-right" : ""}>{l}</span>
      ))}
    </div>
  );
}

const dayShort = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });

// ── 1. the students ──────────────────────────────────────────────────────────

type GroupBy = "none" | "class" | "status";

const STUDENT_COLS = "minmax(0,1.5fr) 10rem 8.5rem minmax(0,1fr) 8.5rem 13rem";

/**
 * Every student with an absence this month, with what the office needs to act.
 *
 * `summary` is composed server-side ("absent 4 of 21 marked days this month · 3
 * in a row right now · sick") so this table, the overview block and Lucy cannot
 * describe the same child differently — the sentence is the computation's, not
 * this component's.
 */
export function AbsenceTable({
  rows, onReason,
}: {
  rows: AbsenceProfile[];
  /** Opens the sheet that turns a red row amber for everybody (D-02 step 3). */
  onReason?: (row: AbsenceProfile) => void;
}) {
  const [q, setQ] = useState("");
  const [klass, setKlass] = useState("all");
  const [only, setOnly] = useState<"all" | "today" | "unexplained">("all");
  const [groupBy, setGroupBy] = useState<GroupBy>("class");

  const classes = useMemo(
    () => Array.from(new Set(rows.map((r) => r.class_label).filter(Boolean))).sort() as string[],
    [rows]);

  const filtered = useMemo(() => rows.filter((r) => {
    if (klass !== "all" && r.class_label !== klass) return false;
    if (only === "today" && !r.absent_today) return false;
    if (only === "unexplained" && r.status !== "unexplained") return false;
    if (q.trim() && !r.full_name.toLowerCase().includes(q.trim().toLowerCase())) return false;
    return true;
  }), [rows, klass, only, q]);

  const groups = useMemo(() => {
    if (groupBy === "none") return [{ key: "", tone: "neutral" as Tone, rows: filtered }];
    const map = new Map<string, AbsenceProfile[]>();
    for (const r of filtered) {
      const key = groupBy === "class"
        ? (r.class_label ? `Class ${r.class_label}` : "No class")
        : r.status === "unexplained" ? "Nobody has explained this" : "Explained";
      const bucket = map.get(key);
      if (bucket) bucket.push(r);
      else map.set(key, [r]);
    }
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([key, rs]) => ({
      key,
      tone: (groupBy === "status"
        ? (key.startsWith("Nobody") ? "red" : "amber")
        : "neutral") as Tone,
      rows: rs,
    }));
  }, [filtered, groupBy]);

  if (!rows.length) {
    return (
      <Empty>
        Nobody has been absent for a whole school day in this window. The table
        fills the moment a student misses every marked period of a day.
      </Empty>
    );
  }

  return (
    <div>
      {/* Filters in one row above the table, never scattered through it. */}
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[160px] flex-1">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input value={q} onChange={(e) => setQ(e.target.value)}
            placeholder="Find a student" className="pl-8" aria-label="Find a student" />
        </div>
        <select value={klass} onChange={(e) => setKlass(e.target.value)} aria-label="Class"
          className="rounded-md border border-border bg-card px-2 py-2 text-sm">
          <option value="all">All classes</option>
          {classes.map((c) => <option key={c} value={c}>Class {c}</option>)}
        </select>
        <select value={only} onChange={(e) => setOnly(e.target.value as typeof only)}
          aria-label="Show"
          className="rounded-md border border-border bg-card px-2 py-2 text-sm">
          <option value="all">Everyone with an absence</option>
          <option value="today">Away right now</option>
          <option value="unexplained">Nobody has explained it</option>
        </select>
        <select value={groupBy} onChange={(e) => setGroupBy(e.target.value as GroupBy)}
          aria-label="Group by"
          className="rounded-md border border-border bg-card px-2 py-2 text-sm">
          <option value="class">Group by class</option>
          <option value="status">Group by explained</option>
          <option value="none">No grouping</option>
        </select>
      </div>

      <p className="mb-3 text-xs text-muted-foreground">
        Showing <span className="font-mono tabular-nums">{filtered.length}</span> of{" "}
        <span className="font-mono tabular-nums">{rows.length}</span>. A row is red when
        a run of three or more school days has no reason on record — an explained
        absence is never red, however long it runs.
      </p>

      {filtered.length === 0 ? (
        <Empty>No student matches those filters.</Empty>
      ) : (
        <div className="-mx-1 overflow-x-auto px-1" style={{ contain: "layout inline-size" }}>
          <div className="min-w-[900px] space-y-4">
            {groups.map((g) => (
              <TableCard key={g.key || "all"}>
                {g.key ? <GroupHeader label={g.key} count={g.rows.length} tone={g.tone} /> : null}
                <HeadRow cols={STUDENT_COLS}
                  labels={["Student", "Parent", "Class teacher", "Reason", "This month", "Act"]} />
                {g.rows.map((r) => (
                  <AbsenceRow key={r.student_id} row={r} onReason={onReason} />
                ))}
              </TableCard>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function AbsenceRow({
  row, onReason,
}: {
  row: AbsenceProfile;
  onReason?: (row: AbsenceProfile) => void;
}) {
  const qc = useQueryClient();
  const remind = useMutation({
    mutationFn: () => insightsApi.action("guardian_reminded", { student_id: row.student_id }),
    onSuccess: (res) => {
      // `already_done` is the rail refusing to pester, not a failure — three
      // people looking at the same absent child in one morning is the normal
      // case, and this is what stops the family getting three messages.
      if (res.already_done) toast.info(res.message);
      else toast.success(res.message);
      qc.invalidateQueries({ queryKey: ["insights"] });
    },
    onError: (e) => showApiError(e, "Could not send the reminder"),
  });

  return (
    <div style={gridStyle(STUDENT_COLS)}
      className={cn("border-b border-border px-3 py-2.5 text-sm transition-colors last:border-0 hover:bg-muted/30",
        ROW_TONE[row.tone])}>
      <div className="min-w-0 pr-3">
        <Link href={`/students/${row.student_id}`}
          className="block truncate font-medium hover:underline">
          {row.full_name}
        </Link>
        <span className="block truncate text-[11px] text-muted-foreground">
          {row.class_label ? `Class ${row.class_label}` : "no class"}
          {row.roll_no ? <span className="font-mono tabular-nums"> · {row.roll_no}</span> : null}
        </span>
      </div>

      <div className="min-w-0 pr-3">
        {row.guardian_name ? (
          <>
            <span className="block truncate text-[12px]">{row.guardian_name}</span>
            {row.guardian_phone ? (
              <a href={`tel:${row.guardian_phone}`}
                className="block font-mono text-[11px] font-medium tabular-nums text-primary hover:underline">
                {row.guardian_phone}
              </a>
            ) : null}
          </>
        ) : (
          <StateChip>no guardian</StateChip>
        )}
      </div>

      <div className="min-w-0 pr-3 text-[12px] text-muted-foreground">
        {row.class_teacher_name ? (
          <span className="flex min-w-0 items-center gap-1.5">
            <Avatar name={row.class_teacher_name} />
            <span className="truncate">{row.class_teacher_name}</span>
          </span>
        ) : <StateChip>none set</StateChip>}
      </div>

      <div className="min-w-0 pr-3">
        {row.status === "explained" ? (
          <span className="block truncate text-[12px] text-muted-foreground">
            {row.reason_note || row.reason_code || "recorded"}
          </span>
        ) : (
          <button type="button" onClick={() => onReason?.(row)}
            className="inline-flex items-center gap-1 rounded-md border border-dashed border-danger/40 px-1.5 py-0.5 text-[11px] text-danger hover:bg-danger/5">
            <NotebookPen className="h-3 w-3" /> Add a reason
          </button>
        )}
      </div>

      <div className="min-w-0 pr-3">
        <span className="flex flex-wrap items-center gap-1.5">
          <Fraction n={row.days_absent} of={row.marked_days} />
          {row.current_streak > 0 ? (
            <Badge tone={TONE_BADGE[row.tone]}>{row.current_streak}d run</Badge>
          ) : null}
        </span>
        {/* The row read aloud — the same sentence every other surface uses. */}
        <span className="mt-0.5 block truncate text-[11px] text-muted-foreground"
          title={row.summary}>
          {row.summary}
        </span>
      </div>

      <div className="flex items-center justify-end gap-1.5">
        {row.reminded_today ? (
          <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-success">
            <Check className="h-3 w-3" /> Reminded
          </span>
        ) : (
          // `D-111`: the DIAGNOSIS is free — this row, this child, this reason
          // all render on every plan. Only the one-tap DISPATCH is paid, so the
          // button keeps its place and opens the upgrade dialog instead.
          <UpgradeGate feature={FEATURES.commsGuardian}>
            <Button size="sm" variant="outline" className="h-7 px-2 text-xs"
              disabled={remind.isPending} onClick={() => remind.mutate()}>
              <MessageSquare className="h-3.5 w-3.5" /> Remind
            </Button>
          </UpgradeGate>
        )}
        <UpgradeGate feature={FEATURES.insightsActions}>
          <FollowUpButton row={row} />
        </UpgradeGate>
      </div>
    </div>
  );
}

/**
 * "Follow up" now asks **who**.
 *
 * It used to fire straight at the server, which defaulted to the class teacher —
 * right often enough to be dangerous, because the admin got a success toast and
 * no idea whose list the task had landed in. The class teacher is still the
 * default and still one tap away; it is just no longer a guess made on the
 * admin's behalf and never shown to them.
 */
function FollowUpButton({ row }: { row: AbsenceProfile }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const [query, setQuery] = useState("");
  const members = useQuery({ queryKey: ["members"], queryFn: appApi.members, enabled: open });

  const assign = useMutation({
    mutationFn: (userId: string | null) =>
      insightsApi.action("followup_assigned", {
        student_id: row.student_id,
        ...(userId ? { user_id: userId } : {}),
        title: `Call ${row.full_name}'s parent — ${row.summary}`,
      }),
    onSuccess: (res) => {
      if (res.already_done) toast.info(res.message);
      else toast.success(res.message);
      setOpen(false); setQuery("");
      qc.invalidateQueries({ queryKey: ["insights"] });
    },
    onError: (e) => showApiError(e, "Could not create the follow-up"),
  });

  if (row.followup_assigned_today) {
    return (
      <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-success">
        <Check className="h-3 w-3" /> Assigned
      </span>
    );
  }

  const list = (members.data?.members ?? []).filter((m) =>
    m.name.toLowerCase().includes(query.toLowerCase()));

  return (
    <>
      <Button size="sm" variant="outline" className="h-7 px-2 text-xs"
        disabled={assign.isPending}
        onClick={(e) => { setRect(e.currentTarget.getBoundingClientRect()); setOpen(true); }}>
        <UserPlus className="h-3.5 w-3.5" /> Follow up
      </Button>

      <Popover open={open} onClose={() => { setOpen(false); setQuery(""); }} rect={rect} width={260}>
        <p className="px-1 pb-1.5 text-[11px] text-muted-foreground">
          Who should call {row.full_name}&rsquo;s family?
        </p>
        {row.class_teacher_name ? (
          <button onClick={() => assign.mutate(null)}
            className="mb-1 flex w-full items-center gap-2 rounded-md border border-border px-2 py-1.5 text-left text-sm hover:bg-muted">
            <Avatar name={row.class_teacher_name} />
            <span className="min-w-0 flex-1 truncate">
              {row.class_teacher_name}
              <span className="block text-[11px] text-muted-foreground">class teacher</span>
            </span>
          </button>
        ) : null}
        <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)}
          placeholder="Search staff…"
          className="mb-1 w-full rounded-md border border-input bg-card px-2 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
        <div className="max-h-56 overflow-y-auto">
          {list.map((m) => (
            <button key={m.user_id} onClick={() => assign.mutate(m.user_id)}
              className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted">
              <Avatar name={m.name} /> <span className="truncate">{m.name}</span>
            </button>
          ))}
          {members.isLoading ? (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">Loading…</p>
          ) : list.length === 0 ? (
            <p className="px-2 py-1.5 text-xs text-muted-foreground">Nobody matches.</p>
          ) : null}
        </div>
      </Popover>
    </>
  );
}

// ── 2. the staff ─────────────────────────────────────────────────────────────

const STAFF_COLS = "minmax(0,1.4fr) minmax(0,1.2fr) 7.5rem 8rem 11rem";

/**
 * Who is away, why, and what it costs in periods.
 *
 * The reason is pre-filled from approved leave when there is one — the admin
 * should never retype what the leave request already says — and the **span** is
 * shown, because cover is arranged for the whole absence and a row that only
 * ever said "today" hid the other two days of a three-day leave.
 */
export function StaffAwayTable({
  rows, onCover,
}: {
  rows: StaffAbsentee[];
  onCover: (row: StaffAbsentee) => void;
}) {
  if (!rows.length) {
    return <Empty>Every teacher is in — there is nothing to cover.</Empty>;
  }
  return (
    <div className="-mx-1 overflow-x-auto px-1" style={{ contain: "layout inline-size" }}>
      <div className="min-w-[740px]">
        <TableCard>
          <HeadRow cols={STAFF_COLS}
            labels={["Teacher", "Reason", "Away", "Uncovered", "Act"]} />
          {rows.map((a) => {
            const gap = Math.max(0, a.periods_due - a.periods_covered);
            const span = a.leave_start && a.leave_end && a.leave_start !== a.leave_end
              ? `${dayShort(a.leave_start)} – ${dayShort(a.leave_end)}`
              : a.date ? dayShort(a.date) : "today";
            return (
              <div key={a.member_id} style={gridStyle(STAFF_COLS)}
                className={cn("border-b border-border px-3 py-2.5 text-sm transition-colors last:border-0 hover:bg-muted/30",
                  gap ? ROW_TONE.red : ROW_TONE.amber)}>
                <div className="flex min-w-0 items-center gap-2 pr-3">
                  <Avatar name={a.name} />
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{a.name}</span>
                    <span className="block text-[11px] text-muted-foreground">{a.role}</span>
                  </span>
                </div>

                <div className="min-w-0 pr-3 text-[12px]">
                  {a.reason ? (
                    <>
                      <span className="block truncate text-muted-foreground">{a.reason}</span>
                      {a.on_leave ? (
                        <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground/70">
                          approved leave
                        </span>
                      ) : null}
                    </>
                  ) : (
                    // Not an error — the admin marked them away without a note.
                    // The fix is on the staff screen, and this says where.
                    <Link href="/staff" className="text-primary hover:underline">
                      <NotebookPen className="mr-1 inline h-3 w-3" />Add a reason
                    </Link>
                  )}
                </div>

                <div className="pr-3 font-mono text-[11px] tabular-nums text-muted-foreground">
                  {span}
                </div>

                <div className="pr-3">
                  {a.periods_due ? (
                    <span className="flex items-center gap-1.5">
                      <Fraction n={gap} of={a.periods_due} />
                      {gap ? null : <Check className="h-3.5 w-3.5 text-success" />}
                    </span>
                  ) : (
                    <StateChip>none that day</StateChip>
                  )}
                </div>

                <div className="flex justify-end">
                  <Button size="sm" variant={gap ? "primary" : "outline"}
                    className="h-7 px-2 text-xs" onClick={() => onCover(a)}>
                    <UserX className="h-3.5 w-3.5" /> Arrange cover
                  </Button>
                </div>
              </div>
            );
          })}
        </TableCard>
      </div>
    </div>
  );
}

// ── 3. the admin desk ────────────────────────────────────────────────────────

const ADMIN_COLS = "minmax(0,1.6fr) 9rem 7rem 15rem";

/**
 * What is sitting on each admin, and the one write this table makes: moving a
 * task to somebody else.
 *
 * Deliberately not automatic. An absent admin's work is not reassigned by the
 * system — a colleague reads the row and decides, because "leave it for them to
 * pick up on Monday" is very often the right answer and no rule can know when.
 */
export function AdminDeskTable({
  rows, options,
}: {
  rows: AdminWorkRow[];
  options: PresenceRow[];
}) {
  if (!rows.length) {
    return <Empty>No admin has open work with a due date.</Empty>;
  }
  return (
    <div className="-mx-1 overflow-x-auto px-1" style={{ contain: "layout inline-size" }}>
      <div className="min-w-[740px] space-y-4">
        {rows.map((w) => (
          <TableCard key={w.member_id}>
            <div className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/40 px-3 py-2 text-sm font-semibold"
              style={{ borderLeft: `3px solid ${BAR[w.tone]}` }}>
              <Avatar name={w.name} />
              {w.name}
              {w.present ? (
                <Badge tone="success">in today</Badge>
              ) : (
                <Badge tone="warning">
                  {w.on_leave ? "on leave" : "away"}{w.reason ? ` — ${w.reason}` : ""}
                </Badge>
              )}
              <span className="ml-auto font-mono text-[10px] font-normal tracking-wide text-muted-foreground">
                {w.summary}
              </span>
            </div>

            {w.rows.length ? (
              <>
                <HeadRow cols={ADMIN_COLS} labels={["Task", "Board", "Due", "Act"]} />
                {w.rows.map((t) => (
                  <TaskRow key={t.task_id} task={t} options={options}
                    currentMemberId={w.member_id} />
                ))}
              </>
            ) : (
              <p className="px-3 py-3 text-xs text-muted-foreground">
                Nothing due or overdue on them today.
              </p>
            )}
          </TableCard>
        ))}
      </div>
    </div>
  );
}

function TaskRow({
  task, options, currentMemberId,
}: {
  task: AdminWorkRow["rows"][number];
  options: PresenceRow[];
  currentMemberId: string;
}) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DOMRect | null>(null);
  const others = options.filter((o) => o.id !== currentMemberId);

  const refresh = () => qc.invalidateQueries({ queryKey: ["insights"] });
  const move = useMutation({
    mutationFn: (memberId: string) =>
      insightsApi.action("task_reassigned", { task_id: task.task_id, member_id: memberId }),
    onSuccess: (res) => { toast.success(res.message); setOpen(false); refresh(); },
    onError: (e) => showApiError(e, "Could not move the task"),
  });
  const extend = useMutation({
    mutationFn: () => insightsApi.action("task_extended", { task_id: task.task_id }),
    onSuccess: (res) => { toast.success(res.message); refresh(); },
    onError: (e) => showApiError(e, "Could not move the due date"),
  });

  return (
    <div style={gridStyle(ADMIN_COLS)}
      className={cn("border-b border-border px-3 py-2.5 text-sm transition-colors last:border-0 hover:bg-muted/30",
        task.days_overdue > 0 ? ROW_TONE.amber : "")}>
      <div className="min-w-0 pr-3">
        <Link href={`/boards/${task.board_id}`}
          className="block truncate font-medium hover:underline">
          {task.title}
        </Link>
        {task.is_critical ? (
          <span className="mt-0.5 inline-block"><Badge tone="danger">critical</Badge></span>
        ) : null}
      </div>
      <div className="min-w-0 truncate pr-3 text-[12px] text-muted-foreground">
        {task.board_name}
      </div>
      <div className="pr-3 font-mono text-[11px] tabular-nums">
        {task.days_overdue > 0 ? (
          <span className="text-warning">{task.days_overdue}d over</span>
        ) : (
          <span className="text-muted-foreground">today</span>
        )}
      </div>
      <div className="flex items-center justify-end gap-1.5">
        {others.length ? (
          <>
            <Button size="sm" variant="outline" className="h-7 px-2 text-xs"
              disabled={move.isPending}
              onClick={(e) => { setRect(e.currentTarget.getBoundingClientRect()); setOpen(true); }}>
              <ArrowRightLeft className="h-3.5 w-3.5" /> Move to
            </Button>
            <Popover open={open} onClose={() => setOpen(false)} rect={rect} width={240}>
              <p className="px-1 pb-1.5 text-[11px] text-muted-foreground">
                Who picks this up?
              </p>
              {others.map((o) => (
                <button key={o.id} onClick={() => move.mutate(o.id)}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted">
                  <Avatar name={o.name} />
                  <span className="min-w-0 flex-1 truncate">
                    {o.name}
                    <span className="block text-[11px] text-muted-foreground">{o.subtitle}</span>
                  </span>
                </button>
              ))}
            </Popover>
          </>
        ) : null}
        {/* "Leave it for them" is a real answer — this is the version of it that
            does not leave the row screaming overdue in the meantime. */}
        <Button size="sm" variant="ghost" className="h-7 px-2 text-xs"
          disabled={extend.isPending} onClick={() => extend.mutate()}>
          <CalendarClock className="h-3.5 w-3.5" /> +1 day
        </Button>
      </div>
    </div>
  );
}
