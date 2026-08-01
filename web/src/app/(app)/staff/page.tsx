"use client";

// Staff attendance — the admin's first job of the day.
//
// The sheet opens with everyone ticked, because on almost every day almost
// everyone is in. The admin unticks the exceptions and saves: that is the whole
// interaction, and it is the same capture-by-exception contract the classroom
// uses for students (P1v2). Nothing is written for the people who came in.
//
// Two things the screen has to be honest about:
//   * an unmarked day is NOT a full house — until someone saves, the header
//     says "not taken yet" rather than showing a reassuring 12/12;
//   * an approved leave has already been decided, so those rows open unticked
//     and say why. The admin still saves the day, so the record is always
//     something a human confirmed.
//
// Saving again replaces the day, so a correction at noon needs no undo.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarOff, Check, CheckCheck, ChevronLeft, ChevronRight, Loader2, UserCheck, Users,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { StaffRosterRow } from "@/lib/school-types";

const ROLE_LABEL: Record<string, string> = { admin: "Admin staff", teacher: "Teachers" };

const iso = (d: Date) => d.toISOString().slice(0, 10);

function pretty(dateStr: string): string {
  const d = new Date(`${dateStr}T00:00:00`);
  const today = iso(new Date());
  if (dateStr === today) return "Today";
  return d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
}

function shift(dateStr: string, days: number): string {
  const d = new Date(`${dateStr}T00:00:00`);
  d.setDate(d.getDate() + days);
  return iso(d);
}

function StaffAttendanceInner() {
  const qc = useQueryClient();
  const [day, setDay] = useState(() => iso(new Date()));
  // null until the sheet loads, then a local working copy the admin edits.
  const [present, setPresent] = useState<Record<string, boolean> | null>(null);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  const { data: sheet, isLoading } = useQuery({
    queryKey: ["staff-attendance", day],
    queryFn: () => schoolApi.staffAttendance(day),
  });

  // Seed the working copy once per day loaded (derived, no effect).
  if (sheet && loadedFor !== day) {
    setPresent(Object.fromEntries(sheet.roster.map((r) => [r.member_id, r.present])));
    setLoadedFor(day);
  }

  const save = useMutation({
    mutationFn: () => schoolApi.markStaffAttendance({
      date: day,
      absent_member_ids: Object.entries(present ?? {})
        .filter(([, isPresent]) => !isPresent)
        .map(([memberId]) => memberId),
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["staff-attendance"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(
        res.absent_count === 0
          ? `Saved — all ${res.total} staff present`
          : `Saved — ${res.present_count}/${res.total} present, ${res.absent_count} away`);
    },
    onError: (e) => showApiError(e, "Could not save staff attendance"),
  });

  const goto = (days: number) => { setDay(shift(day, days)); };

  const rows = sheet?.roster ?? [];
  const presentCount = Object.values(present ?? {}).filter(Boolean).length;
  const dirty = !!sheet && !!present
    && rows.some((r) => (present[r.member_id] ?? true) !== r.present);
  const isFuture = day > iso(new Date());

  // Group by role so an admin scanning for a missing teacher isn't reading past
  // the office staff — the two populations are managed differently.
  const groups = new Map<string, StaffRosterRow[]>();
  for (const r of rows) {
    if (!groups.has(r.role)) groups.set(r.role, []);
    groups.get(r.role)!.push(r);
  }

  return (
    <div className="pb-8">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <PageHeader title="Staff attendance" subtitle="Untick whoever is away, then save." />
        <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-1">
          <Button size="sm" variant="ghost" onClick={() => goto(-1)} aria-label="Previous day">
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span className="min-w-[7.5rem] text-center text-sm font-medium">{pretty(day)}</span>
          <Button size="sm" variant="ghost" onClick={() => goto(1)} aria-label="Next day"
            disabled={isFuture}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isLoading || !sheet || !present ? (
        <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
      ) : (
        <>
          {/* The status band. Says plainly whether anyone has confirmed the day. */}
          <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
            <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-md ${sheet.marked ? "bg-[color:var(--success,#234a37)]/10 text-[color:var(--success,#234a37)]" : "bg-muted text-muted-foreground"}`}>
              <Users className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold">
                {sheet.marked
                  ? `${presentCount} of ${sheet.total} present`
                  : `${sheet.total} staff on the roll`}
              </p>
              <p className="text-xs text-muted-foreground">
                {sheet.marked
                  ? `Taken by ${sheet.marked_by ?? "an admin"}${sheet.marked_at ? ` at ${new Date(sheet.marked_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}` : ""}`
                  : "Not taken yet — nobody has confirmed this day"}
              </p>
            </div>
            {sheet.marked ? (
              <Badge tone={sheet.absent_count ? "warning" : "success"}>
                {sheet.absent_count ? `${sheet.absent_count} away` : "full house"}
              </Badge>
            ) : (
              <Badge tone="neutral">not taken</Badge>
            )}
          </div>

          {rows.length === 0 ? (
            <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
              No staff on the roll yet. Add them in Setup → Members.
            </p>
          ) : (
            <>
              <div className="mb-2 flex items-center justify-end">
                <Button size="sm" variant="ghost"
                  onClick={() => setPresent(Object.fromEntries(rows.map((r) => [r.member_id, true])))}>
                  <CheckCheck className="h-4 w-4" /> Tick everyone
                </Button>
              </div>

              {[...groups.entries()].map(([role, members]) => (
                <section key={role} className="mb-4">
                  <h2 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {ROLE_LABEL[role] ?? role} · {members.length}
                  </h2>
                  <div className="grid gap-1 sm:grid-cols-2">
                    {members.map((r) => {
                      const on = present[r.member_id] ?? true;
                      return (
                        <button key={r.member_id} type="button"
                          onClick={() => setPresent({ ...present, [r.member_id]: !on })}
                          aria-pressed={on}
                          className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-sm active:scale-[0.99] ${on ? "border-[color:var(--success,#234a37)]/40 bg-[color:var(--success,#234a37)]/5" : "border-border bg-card"}`}>
                          <span className={`grid h-5 w-5 shrink-0 place-items-center rounded border ${on ? "border-[color:var(--success,#234a37)] bg-[color:var(--success,#234a37)] text-white" : "border-border bg-background"}`}>
                            {on ? <Check className="h-3.5 w-3.5" /> : null}
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate">{r.name}</span>
                            {r.on_leave ? (
                              <span className="block truncate text-xs text-muted-foreground">
                                Approved leave — {r.leave_reason}
                              </span>
                            ) : null}
                          </span>
                          {r.on_leave ? (
                            <Badge tone="outline"><CalendarOff className="h-3 w-3" /> leave</Badge>
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                </section>
              ))}

              <Button className="w-full" disabled={save.isPending} onClick={() => save.mutate()}>
                {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserCheck className="h-4 w-4" />}
                {save.isPending
                  ? "Saving…"
                  : sheet.marked && !dirty
                    ? `Saved — ${presentCount}/${sheet.total} present`
                    : `${sheet.marked ? "Update" : "Save"} attendance — ${presentCount}/${sheet.total} present`}
              </Button>
              {sheet.marked ? (
                <p className="mt-2 text-center text-xs text-muted-foreground">
                  You can come back and change this any time.
                </p>
              ) : null}
            </>
          )}
        </>
      )}
    </div>
  );
}

export default function StaffAttendancePage() {
  return (
    <AuthGuard allow={["admin"]}>
      <StaffAttendanceInner />
    </AuthGuard>
  );
}
