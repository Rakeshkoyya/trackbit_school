"use client";

// Staff attendance — the admin's first job of the day.
//
// The sheet opens with everyone present, because on almost every day almost
// everyone is in. The admin taps the exceptions and saves: that is the whole
// interaction, and it is the same capture-by-exception contract the classroom
// uses for students (P1v2). Nothing is written for the people who came in.
//
// V1-4 (`D-04`) gave the tap four states instead of two — present · half day ·
// late · away — and a half day asks which half, because the cover board's whole
// job is knowing which periods need filling and "0.5 days" cannot answer that
// (`S-31`). Late is still PRESENT: it is a flag to be seen, never a deduction.
//
// Two things the screen has to be honest about:
//   * an unmarked day is NOT a full house — until someone saves, the header
//     says "not taken yet" rather than showing a reassuring 12/12;
//   * an approved leave has already been decided, so those rows open away (or
//     half-day, if that is what was approved) and say why. The admin still
//     saves the day, so the record is always something a human confirmed.
//
// Saving again replaces the day, so a correction at noon needs no undo.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CalendarOff, Check, CheckCheck, ChevronLeft, ChevronRight, Clock, Loader2,
  Sunrise, Sunset, UserCheck, Users, X,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { showApiError } from "@/lib/errors";
import { dayKey, todayKey } from "@/lib/format";
import { schoolApi } from "@/lib/school-api";
import type { StaffDayStatus, StaffRosterRow } from "@/lib/school-types";

const ROLE_LABEL: Record<string, string> = { admin: "Admin staff", teacher: "Teachers" };

/** One tap moves to the next state; the fourth returns to present. Half day
 *  then asks which half — the only follow-up question in the flow. */
const CYCLE: StaffDayStatus[] = ["present", "absent", "half_day", "late"];

const STATE: Record<StaffDayStatus, { label: string; icon: typeof Check; className: string }> = {
  present: {
    label: "In", icon: Check,
    className: "border-[color:var(--success,#234a37)]/40 bg-[color:var(--success,#234a37)]/5",
  },
  absent: { label: "Away", icon: X, className: "border-danger/40 bg-danger-soft" },
  half_day: { label: "Half day", icon: Sunrise, className: "border-warning/40 bg-warning-soft" },
  late: { label: "Late", icon: Clock, className: "border-border bg-card" },
};


function pretty(dateStr: string): string {
  const d = new Date(`${dateStr}T00:00:00`);
  const today = todayKey();
  if (dateStr === today) return "Today";
  return d.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
}

function shift(dateStr: string, days: number): string {
  const d = new Date(`${dateStr}T00:00:00`);
  d.setDate(d.getDate() + days);
  return dayKey(d);
}

type Mark = { status: StaffDayStatus; portion: "am" | "pm" | null };

function StaffAttendanceInner() {
  const qc = useQueryClient();
  const [day, setDay] = useState(() => todayKey());
  // null until the sheet loads, then a local working copy the admin edits.
  const [marks, setMarks] = useState<Record<string, Mark> | null>(null);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);

  const { data: sheet, isLoading } = useQuery({
    queryKey: ["staff-attendance", day],
    queryFn: () => schoolApi.staffAttendance(day),
  });

  // Seed the working copy once per day loaded (derived, no effect).
  if (sheet && loadedFor !== day) {
    setMarks(Object.fromEntries(sheet.roster.map((r) =>
      [r.member_id, { status: r.status, portion: r.portion }])));
    setLoadedFor(day);
  }

  const save = useMutation({
    mutationFn: () => schoolApi.markStaffAttendance({
      date: day,
      // Only deviations travel — present people are never sent (P1v2).
      marks: Object.entries(marks ?? {})
        .filter(([, mark]) => mark.status !== "present")
        .map(([member_id, mark]) => ({
          member_id,
          status: mark.status as "absent" | "half_day" | "late",
          portion: mark.status === "half_day" ? (mark.portion ?? "am") : null,
        })),
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["staff-attendance"] });
      qc.invalidateQueries({ queryKey: ["staff-month"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      qc.invalidateQueries({ queryKey: ["insights"] });
      toast.success(
        res.absent_count === 0 && res.late_count === 0
          ? `Saved — all ${res.total} staff present`
          : `Saved — ${res.present_days} of ${res.total} days worked`);
    },
    onError: (e) => showApiError(e, "Could not save staff attendance"),
  });

  const goto = (days: number) => { setDay(shift(day, days)); };

  const rows = sheet?.roster ?? [];
  const at = (id: string): Mark => marks?.[id] ?? { status: "present", portion: null };
  const setMark = (id: string, next: Mark) =>
    setMarks({ ...(marks ?? {}), [id]: next });
  const cycle = (id: string) => {
    const current = at(id).status;
    const next = CYCLE[(CYCLE.indexOf(current) + 1) % CYCLE.length];
    setMark(id, { status: next, portion: next === "half_day" ? "am" : null });
  };
  // "In" is present + late — late is a flag on somebody who came (D-04/S-19).
  const inCount = rows.filter((r) => at(r.member_id).status !== "absent"
    && at(r.member_id).status !== "half_day").length;
  const halfCount = rows.filter((r) => at(r.member_id).status === "half_day").length;
  const dirty = !!sheet && !!marks
    && rows.some((r) => at(r.member_id).status !== r.status
      || (at(r.member_id).status === "half_day" && at(r.member_id).portion !== r.portion));
  const isFuture = day > todayKey();

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

      {isLoading || !sheet || !marks ? (
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
                  ? `${inCount} of ${sheet.total} in${halfCount ? ` · ${halfCount} half day` : ""}`
                  : `${sheet.total} staff on the roll`}
              </p>
              <p className="text-xs text-muted-foreground">
                {sheet.marked
                  ? `${sheet.present_days} days worked · taken by ${sheet.marked_by ?? "an admin"}${sheet.marked_at ? ` at ${new Date(sheet.marked_at).toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit" })}` : ""}`
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
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs text-muted-foreground">
                  Tap a name to cycle: in → away → half day → late.
                </p>
                <Button size="sm" variant="ghost"
                  onClick={() => setMarks(Object.fromEntries(
                    rows.map((r) => [r.member_id, { status: "present", portion: null }])))}>
                  <CheckCheck className="h-4 w-4" /> Everyone in
                </Button>
              </div>

              {[...groups.entries()].map(([role, members]) => (
                <section key={role} className="mb-4">
                  <h2 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {ROLE_LABEL[role] ?? role} · {members.length}
                  </h2>
                  <div className="grid gap-1 sm:grid-cols-2">
                    {members.map((r) => {
                      const mark = at(r.member_id);
                      const state = STATE[mark.status];
                      const Icon = state.icon;
                      return (
                        <div key={r.member_id}
                          className={`rounded-lg border ${state.className}`}>
                          <button type="button" onClick={() => cycle(r.member_id)}
                            className="flex w-full items-center gap-3 px-3 py-2.5 text-left text-sm active:scale-[0.99]">
                            <span className="grid h-5 w-5 shrink-0 place-items-center rounded border border-border/60 bg-background/70">
                              <Icon className="h-3.5 w-3.5" />
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
                            <span className="shrink-0 text-xs font-medium text-muted-foreground">
                              {state.label}
                            </span>
                          </button>

                          {/* A half day is not half a fact — it has to say which
                              half, or the cover board cannot name the periods. */}
                          {mark.status === "half_day" ? (
                            <div className="flex gap-1.5 border-t border-border/60 px-3 py-2">
                              {(["am", "pm"] as const).map((half) => {
                                const active = (mark.portion ?? "am") === half;
                                const HalfIcon = half === "am" ? Sunrise : Sunset;
                                return (
                                  <button key={half} type="button" aria-pressed={active}
                                    onClick={() => setMark(r.member_id,
                                      { status: "half_day", portion: half })}
                                    className={`flex flex-1 items-center justify-center gap-1.5 rounded-md border px-2 py-1 text-xs font-medium ${active ? "border-primary bg-accent text-accent-foreground" : "border-border bg-background text-muted-foreground"}`}>
                                    <HalfIcon className="h-3 w-3" />
                                    away {half === "am" ? "morning" : "afternoon"}
                                  </button>
                                );
                              })}
                            </div>
                          ) : null}
                        </div>
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
                    ? `Saved — ${inCount}/${sheet.total} in`
                    : `${sheet.marked ? "Update" : "Save"} attendance — ${inCount}/${sheet.total} in`}
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
