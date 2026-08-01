"use client";

// One student's homework record (V1-5 — `S-86`, `S-101`, `D-31`).
//
// **Built once, mounted twice.** This is the teacher's by-student view on
// `/homework` *and* the admin's drill-down from `/dashboard/homework`'s red
// list. The endpoint has existed since HW-1 and was called by nothing; the two
// screens ask the identical question — *"how is this child doing with
// homework?"* — so two components would have been two answers.
//
// The load-bearing rule, from HW-1 and re-asserted all through V1-5:
// **`not_checked` is the teacher's gap, never the child's.** It is counted
// apart, kept out of every completion figure, and never rendered as a miss.
// Same for `carried`: a child who was absent when the work was set never
// refused it (`D-34`), so it is neutral, out of the denominator, and out of the
// streak.

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { schoolApi } from "@/lib/school-api";
import type { HomeworkStatus } from "@/lib/school-types";
import { cn } from "@/lib/utils";

/** How each verdict reads. Note what is NOT red: `carried` (they were away) and
 *  `not_checked` (nobody has looked). Colouring either would put a child off
 *  sick, or a teacher's backlog, on a list about the child. */
const STATUS: Record<HomeworkStatus, { label: string; tone: "success" | "warning" | "danger" | "neutral" }> = {
  done: { label: "did it", tone: "success" },
  late: { label: "did it, late", tone: "success" },
  partial: { label: "partly", tone: "warning" },
  not_done: { label: "didn’t", tone: "danger" },
  carried: { label: "was away", tone: "neutral" },
  waived: { label: "let go", tone: "neutral" },
  not_checked: { label: "not checked yet", tone: "neutral" },
};

function Tile({ label, value, sub, tone = "neutral" }: {
  label: string; value: string; sub?: string;
  tone?: "success" | "warning" | "danger" | "neutral";
}) {
  const colour = {
    success: "text-success", warning: "text-warning",
    danger: "text-danger", neutral: "text-foreground",
  }[tone];
  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2">
      <p className="text-[11px] text-muted-foreground">{label}</p>
      <p className={cn("text-lg font-semibold tabular-nums", colour)}>{value}</p>
      {sub ? <p className="text-[11px] text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

export function StudentHomeworkHistory({
  studentId, windowDays = 30, showName = false,
}: {
  studentId: string;
  windowDays?: number;
  showName?: boolean;
}) {
  const [days, setDays] = useState(windowDays);
  const { data, isLoading } = useQuery({
    queryKey: ["homework-student", studentId, days],
    queryFn: () => schoolApi.studentHomework(studentId, days),
  });

  if (isLoading) return <div className="h-32 animate-pulse rounded-xl bg-muted" />;
  if (!data) return null;

  const graded = data.done + data.late + data.partial + data.not_done;

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {showName ? (
          <p className="text-sm font-semibold">
            {data.full_name}
            {data.class_label ? <span className="font-normal text-muted-foreground"> · {data.class_label}</span> : null}
          </p>
        ) : null}
        <div className="ml-auto flex gap-1 rounded-lg border border-border p-0.5">
          {[14, 30, 90].map((d) => (
            <button key={d} type="button" onClick={() => setDays(d)}
              className={cn("rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                d === days ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground")}>
              {d}d
            </button>
          ))}
        </div>
      </div>

      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {/* The denominator is stated, and it is `graded` — not `assigned` —
            because carried, waived and not_checked are outside it. */}
        <Tile label="Completion"
          value={data.completion != null ? `${Math.round(data.completion * 100)}%` : "—"}
          sub={data.completion != null ? `of ${graded} checked` : "nothing checked yet"}
          tone={data.completion == null ? "neutral"
            : data.completion >= 0.8 ? "success" : data.completion >= 0.5 ? "warning" : "danger"} />
        <Tile label="Didn’t do it" value={String(data.not_done)}
          sub={data.partial ? `${data.partial} partly` : undefined}
          tone={data.not_done ? "danger" : "neutral"} />
        <Tile label="Missed in a row" value={String(data.streak)}
          sub={data.streak ? "school days" : "no run"}
          tone={data.streak >= 3 ? "danger" : data.streak ? "warning" : "success"} />
        {/* Reported beside completion, never inside it. */}
        <Tile label="Late · was away" value={`${data.late} · ${data.carried}`}
          sub={data.not_checked ? `${data.not_checked} not checked yet` : "all checked"} />
      </div>

      {data.items.length ? (
        <ul className="space-y-1.5">
          {data.items.map((it) => {
            const s = STATUS[it.status as HomeworkStatus] ?? STATUS.not_checked;
            return (
              <li key={`${it.assignment_id}-${it.date}`}
                className="flex flex-wrap items-baseline gap-2 rounded-lg border border-border bg-card px-3 py-2 text-sm">
                <span className="w-20 shrink-0 text-xs text-muted-foreground">{it.date.slice(5)}</span>
                <span className="w-24 shrink-0 truncate text-xs font-medium">{it.subject_name ?? "—"}</span>
                <span className="min-w-0 flex-1">
                  {it.text}
                  {it.personal ? (
                    <span className="ml-1 text-xs text-muted-foreground">(just for them)</span>
                  ) : null}
                  {it.note ? (
                    <span className="block text-xs text-muted-foreground">{it.note}</span>
                  ) : null}
                </span>
                <Badge tone={s.tone}>{s.label}</Badge>
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
          No homework recorded for {data.full_name} in the last {days} days.
        </p>
      )}
    </div>
  );
}
