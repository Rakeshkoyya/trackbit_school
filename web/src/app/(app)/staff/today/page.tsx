"use client";

// Today — where every member of staff is, period by period.
//
// This is the payoff of the timesheet: the timetable already knew who was
// teaching, and now the periods in between are filled in too. Reading down a
// column tells the admin who is genuinely free right now, which is the question
// they ask whenever something needs covering.
//
// The grid is one payload (`/staff/timesheet/today`) — three queries server-side
// regardless of headcount — because a per-teacher fetch would be one remote
// round-trip per person.

import { useQuery } from "@tanstack/react-query";
import { BookOpen, Clock, Users } from "lucide-react";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { schoolApi } from "@/lib/school-api";
import type { TimesheetSlot } from "@/lib/school-types";

const iso = (d: Date) => d.toISOString().slice(0, 10);

/** Cell styling carries the meaning: taught periods read solid, cover reads
 *  accent (they're in a colleague's class — S-72), recorded work reads quiet,
 *  away reads struck out, and free reads empty — a gap visible at a glance. */
function cellClass(kind: TimesheetSlot["kind"]): string {
  if (kind === "class") return "bg-[color:var(--success,#234a37)]/12 text-foreground";
  if (kind === "cover") return "bg-primary/10 text-foreground";
  if (kind === "work") return "bg-muted text-muted-foreground";
  if (kind === "away") return "bg-muted/50 text-muted-foreground/50";
  return "bg-background text-muted-foreground/40";
}

function cellText(slot: TimesheetSlot): string {
  if (slot.kind === "class") return slot.subject_name ?? "Class";
  if (slot.kind === "cover") return `⟳ ${slot.subject_name ?? slot.class_label ?? "Cover"}`;
  if (slot.kind === "work") return slot.work_label ?? "Work";
  if (slot.kind === "away") return "Away";
  return "—";
}

function StaffTodayInner() {
  const [day] = useState(() => iso(new Date()));
  const { data = [], isLoading } = useQuery({
    queryKey: ["staff-today", day],
    queryFn: () => schoolApi.orgTimesheetToday(day),
  });

  const periods = data[0]?.days[0]?.slots.map((s) => s.period_no) ?? [];
  const teachingNow = data.filter((r) => r.teaching_periods + r.covered_periods > 0).length;
  const totalFree = data.reduce((sum, r) => sum + r.free_periods, 0);
  const awayCount = data.filter((r) => r.away_reason).length;

  return (
    <div className="pb-8">
      <PageHeader title="Today" subtitle="Who is teaching, who is on other work, who is free." />

      {isLoading ? (
        <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
      ) : data.length === 0 || periods.length === 0 ? (
        <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          Nothing to show yet — set the school timings in Plan → Timetable, and the day fills in
          from the grid.
        </p>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-3 gap-3">
            {[
              { label: "Staff", value: awayCount ? `${data.length - awayCount} in · ${awayCount} away` : data.length, icon: Users },
              { label: "Teaching today", value: teachingNow, icon: BookOpen },
              { label: "Free periods", value: totalFree, icon: Clock },
            ].map((t) => (
              <div key={t.label} className="rounded-xl border border-border bg-card px-4 py-3">
                <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <t.icon className="h-3.5 w-3.5" /> {t.label}
                </p>
                <p className="mt-0.5 text-xl font-semibold tabular-nums">{t.value}</p>
              </div>
            ))}
          </div>

          {/* Wide content scrolls inside its own container — the page never does. */}
          <div className="overflow-x-auto rounded-xl border border-border bg-card">
            <table className="w-full min-w-[42rem] border-collapse text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="sticky left-0 z-10 bg-card px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Staff
                  </th>
                  {periods.map((p) => (
                    <th key={p} className="px-2 py-2.5 text-center text-xs font-semibold text-muted-foreground">
                      P{p}
                    </th>
                  ))}
                  <th className="px-3 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Load
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.map((row) => {
                  const slots = row.days[0]?.slots ?? [];
                  return (
                    <tr key={row.member_id} className="border-b border-border last:border-0">
                      <td className="sticky left-0 z-10 max-w-[10rem] truncate bg-card px-4 py-2 font-medium">
                        {row.member_name}
                      </td>
                      {slots.map((s) => (
                        <td key={s.period_no} className="px-1 py-1 text-center">
                          <span
                            title={s.kind === "class"
                              ? `${s.class_label} · ${s.subject_name}`
                              : s.note ?? cellText(s)}
                            className={`block truncate rounded px-1.5 py-1.5 text-[11px] ${cellClass(s.kind)}`}>
                            {cellText(s)}
                          </span>
                        </td>
                      ))}
                      <td className="px-3 py-2 text-right">
                        {row.away_reason ? (
                          <Badge tone="neutral">Away · {row.away_reason}</Badge>
                        ) : (
                          <Badge tone={row.free_periods === slots.length ? "neutral" : "outline"}>
                            {row.teaching_periods + row.covered_periods + row.work_periods}/{slots.length}
                          </Badge>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            Teaching periods come from the timetable. The rest is what each teacher recorded on
            their own timesheet.
          </p>
        </>
      )}
    </div>
  );
}

export default function StaffTodayPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <StaffTodayInner />
    </AuthGuard>
  );
}
