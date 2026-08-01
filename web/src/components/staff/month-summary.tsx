"use client";

// The staff month summary (`D-78`) — one component, two screens.
//
// > *"I want number of days the teacher worked out of working days, so I have
// > information of the staff month."*
//
// **There is no money on this screen and no path from it to one** (`D-25`).
// Payroll is a v2 packet; what v1 owes it is a correct input.
//
// The load-bearing rule is `S-34`: **a day nobody marked is `not marked`, never
// absent.** It gets its own column, in its own word, in neutral grey, and it is
// excluded from days worked. Today that is a display rule. The moment this
// figure informs pay it is the difference between a clerical gap and an unpaid
// day, so it is computed that way on the server too and rendered that way here.
//
// The admin sees everyone; a teacher sees herself — because a person whose
// attendance record is being kept must be able to read it, or a disputed figure
// has no evidence the person disputing it can see.

import { useQuery } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { schoolApi } from "@/lib/school-api";
import type { StaffMonthRow } from "@/lib/school-types";

const ROLE_LABEL: Record<string, string> = { admin: "Admin staff", teacher: "Teachers" };

function shiftMonth(month: string, by: number): string {
  const [y, m] = month.split("-").map(Number);
  const total = y * 12 + (m - 1) + by;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}

function monthLabel(month: string): string {
  return new Date(`${month}-01T00:00:00`).toLocaleDateString("en-IN", {
    month: "long", year: "numeric" });
}

function dayLabel(d: string): string {
  return new Date(`${d}T00:00:00`).toLocaleDateString("en-IN", {
    day: "numeric", month: "short" });
}

/** "1" not "1.0", "1.5" as itself — half-days are the whole point of the column. */
const n = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1));

function Row({ row, single }: { row: StaffMonthRow; single: boolean }) {
  return (
    <tr className="border-b border-border/60">
      {single ? null : (
        <td className="py-2 pr-3">
          <span className="block truncate">{row.name}</span>
          <span className="block text-xs text-muted-foreground">{row.role}</span>
        </td>
      )}
      <td className="py-2 pr-3 text-right tabular-nums">
        <span className="font-medium">{n(row.days_present)}</span>
        <span className="text-muted-foreground"> / {row.working_days}</span>
      </td>
      <td className="py-2 pr-3 text-right tabular-nums text-muted-foreground">
        {n(row.days_absent)}
      </td>
      <td className="py-2 pr-3 text-right tabular-nums text-muted-foreground">
        {row.half_days || "—"}
      </td>
      <td className="py-2 pr-3 text-right tabular-nums text-muted-foreground">
        {row.lates || "—"}
      </td>
      {/* S-34 — a word, in neutral grey, never red and never an absence. */}
      <td className="py-2 pr-3 text-right tabular-nums">
        {row.days_not_marked ? (
          <span className="text-muted-foreground">{row.days_not_marked} not marked</span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </td>
      <td className="py-2 pr-3 text-right tabular-nums">{n(row.leave_days)}</td>
      <td className="py-2 text-right tabular-nums text-muted-foreground">
        {n(row.leave_remaining)}
      </td>
    </tr>
  );
}

export function StaffMonthSummary({ mine = false }: { mine?: boolean }) {
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7));
  const { data, isLoading } = useQuery({
    queryKey: ["staff-month", month, mine],
    queryFn: () => schoolApi.staffMonth({ month }),
  });

  const rows = data?.rows ?? [];
  const groups = new Map<string, StaffMonthRow[]>();
  for (const r of rows) {
    if (!groups.has(r.role)) groups.set(r.role, []);
    groups.get(r.role)!.push(r);
  }
  const single = mine || rows.length === 1;

  return (
    <div className="pb-8">
      <div className="mb-4 flex items-center gap-1 rounded-lg border border-border bg-card p-1 w-fit">
        <Button size="sm" variant="ghost" aria-label="Previous month"
          onClick={() => setMonth(shiftMonth(month, -1))}>
          <ChevronLeft className="h-4 w-4" />
        </Button>
        <span className="min-w-[9.5rem] text-center text-sm font-medium">{monthLabel(month)}</span>
        <Button size="sm" variant="ghost" aria-label="Next month"
          onClick={() => setMonth(shiftMonth(month, 1))}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      {isLoading || !data ? (
        <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
      ) : data.working_days === 0 ? (
        <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          This month hasn’t started yet.
        </p>
      ) : (
        <>
          {/* Lead with the sentence, and say which window it used — a month in
              progress is not a month where everyone stopped coming (ux §4). */}
          <div className="mb-4 rounded-xl border border-border bg-card px-4 py-3">
            <p className="text-sm">
              <span className="font-semibold">{data.working_days} working days</span>
              {" "}so far this month — {dayLabel(data.start_date)} to {dayLabel(data.end_date)}.
              {" "}Attendance was taken on <span className="font-semibold">{data.days_marked}</span> of them.
            </p>
            {data.working_days > data.days_marked ? (
              <p className="mt-1 text-xs text-muted-foreground">
                {data.working_days - data.days_marked} day
                {data.working_days - data.days_marked === 1 ? "" : "s"} nobody marked. Those are a
                gap in the record, not absences — they are counted separately and never as a
                shortfall against anyone.
              </p>
            ) : null}
            <p className="mt-1 text-xs text-muted-foreground">
              Days worked, leave and balance only. No pay figures anywhere in TrackBit.
            </p>
          </div>

          {rows.length === 0 ? (
            <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
              No staff on the roll yet.
            </p>
          ) : single ? (
            <div className="overflow-x-auto rounded-xl border border-border bg-card p-3">
              <MonthTable rows={rows} single />
            </div>
          ) : (
            [...groups.entries()].map(([role, members]) => (
              <section key={role} className="mb-4">
                <h2 className="mb-1.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {ROLE_LABEL[role] ?? role}
                  <Badge tone="outline">{members.length}</Badge>
                </h2>
                <div className="overflow-x-auto rounded-xl border border-border bg-card p-3">
                  <MonthTable rows={members} single={false} />
                </div>
              </section>
            ))
          )}
        </>
      )}
    </div>
  );
}

function MonthTable({ rows, single }: { rows: StaffMonthRow[]; single: boolean }) {
  return (
    <table className="w-full min-w-[560px] text-sm">
      <thead>
        <tr className="border-b border-border text-left text-xs text-muted-foreground">
          {single ? null : <th className="py-2 pr-3 font-medium">Name</th>}
          <th className="py-2 pr-3 text-right font-medium">Days worked</th>
          <th className="py-2 pr-3 text-right font-medium">Away</th>
          <th className="py-2 pr-3 text-right font-medium">Half days</th>
          <th className="py-2 pr-3 text-right font-medium">Late</th>
          <th className="py-2 pr-3 text-right font-medium">Not marked</th>
          <th className="py-2 pr-3 text-right font-medium">Leave used</th>
          <th className="py-2 text-right font-medium">Leave left</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => <Row key={r.member_id} row={r} single={single} />)}
      </tbody>
    </table>
  );
}
