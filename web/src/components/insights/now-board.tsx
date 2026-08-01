"use client";

// The live period board (DASH3 §4.3).
//
//     Period 4 · 11:20–12:00 — 9 teaching · 4 free · 2 absent
//
// Every list is named, because "4 free" is not actionable and "Priya, Anil,
// Ramesh, Meera are free" is. What the working ones are doing comes from the
// timesheet (SF-1) — real capture, not an inference from task categories.
//
// It degrades honestly rather than inventing a period: before/after school,
// break, holiday, and `unset` when the school never entered its timings. A
// dashboard that says "Period 4" on a Sunday has stopped being trustworthy.

import { BookOpen, Coffee, Moon, Sun, UserX, Wrench } from "lucide-react";
import type { ReactNode } from "react";

import type { NowBoard as NowBoardData, NowPerson } from "@/lib/insights-types";

import { Empty } from "./shared";

const PHASE: Record<NowBoardData["phase"], { label: string; icon: ReactNode }> = {
  period: { label: "In lessons", icon: <BookOpen className="h-4 w-4" /> },
  break: { label: "Break", icon: <Coffee className="h-4 w-4" /> },
  before: { label: "Before school", icon: <Sun className="h-4 w-4" /> },
  after: { label: "After school", icon: <Moon className="h-4 w-4" /> },
  holiday: { label: "School closed", icon: <Moon className="h-4 w-4" /> },
  unset: { label: "Timings not set", icon: <Wrench className="h-4 w-4" /> },
};

function PeopleColumn({
  title, icon, people, empty, describe,
}: {
  title: string;
  icon: ReactNode;
  people: NowPerson[];
  empty: string;
  describe: (p: NowPerson) => string | null;
}) {
  return (
    <div className="min-w-0">
      <p className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {icon} {title}
        <span className="tabular-nums">{people.length}</span>
      </p>
      {people.length ? (
        <ul className="space-y-1">
          {people.map((p) => {
            const detail = describe(p);
            return (
              <li key={p.member_id} className="truncate text-sm">
                {p.name}
                {detail ? <span className="text-muted-foreground"> · {detail}</span> : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="text-sm text-muted-foreground">{empty}</p>
      )}
    </div>
  );
}

export function NowBoard({ board }: { board: NowBoardData }) {
  const phase = PHASE[board.phase] ?? PHASE.unset;
  const heading = board.phase === "period" && board.period_no
    ? `Period ${board.period_no}${board.period_start ? ` · ${board.period_start}–${board.period_end}` : ""}`
    : phase.label;

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1.5 text-sm font-semibold">
          {phase.icon} {heading}
        </span>
        <span className="text-xs text-muted-foreground">· as of {board.now.slice(0, 5)}</span>
        {!board.staff_marked ? (
          <span className="ml-auto text-xs text-muted-foreground">
            staff attendance not taken — “away” may be incomplete
          </span>
        ) : null}
      </div>

      {board.phase === "period" ? (
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <PeopleColumn
            title="Teaching" icon={<BookOpen className="h-3.5 w-3.5" />}
            people={board.teaching} empty="Nobody is in a classroom."
            describe={(p) => [p.class_label, p.subject_name, p.substituting ? "covering" : null]
              .filter(Boolean).join(" ") || null}
          />
          <PeopleColumn
            title="On other work" icon={<Wrench className="h-3.5 w-3.5" />}
            people={board.working} empty="Nothing recorded on the timesheet."
            describe={(p) => p.note ? `${p.work_label} — ${p.note}` : p.work_label}
          />
          <PeopleColumn
            title="Free" icon={<Coffee className="h-3.5 w-3.5" />}
            people={board.free} empty="Everyone is accounted for."
            describe={(p) => p.open_tasks ? `${p.open_tasks} open task${p.open_tasks === 1 ? "" : "s"}` : "nothing assigned"}
          />
          <PeopleColumn
            title="Away" icon={<UserX className="h-3.5 w-3.5" />}
            people={board.absent} empty="Everyone is in."
            describe={(p) => p.reason}
          />
        </div>
      ) : board.absent.length ? (
        <div>
          <p className="mb-2 text-sm text-muted-foreground">
            No lesson is running right now. Away today:
          </p>
          <ul className="space-y-1">
            {board.absent.map((p) => (
              <li key={p.member_id} className="truncate text-sm">
                {p.name}{p.reason ? <span className="text-muted-foreground"> · {p.reason}</span> : null}
              </li>
            ))}
          </ul>
        </div>
      ) : (
        <Empty>
          {board.phase === "unset"
            ? "Set the school timings in Plan → Timetable and this board comes alive."
            : "No lesson is running right now, and everyone is in."}
        </Empty>
      )}
    </div>
  );
}
