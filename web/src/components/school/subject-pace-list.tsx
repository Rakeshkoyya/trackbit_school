"use client";

// One row per class-subject, saying where it is and what to teach next.
//
// Shared by the teacher's **My subjects** (`S-46`) and the class teacher's
// **My class's syllabus** block (`S-28`, `D-15`) — the same rendering of the
// same computation, differing only in which rows the server was willing to
// hand over. Building it twice is how the two would drift into showing a
// teacher two different figures about herself.
//
// Rules it must not break:
//   * `unknown` is a WORD, never a colour (`S-42`). A subject she has not
//     logged is not a subject she is behind in.
//   * every figure carries its denominator (rule 3) — "12 of 18 planned",
//     never a bare 67%.
//   * never a rank, never a league table, and no pace figure from here reaches
//     a parent (`D-11`).

import Link from "next/link";
import { ArrowRight } from "lucide-react";

import { StateChip } from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import type { SubjectPaceRow } from "@/lib/school-types";

/** green/amber/red are pace; everything else is a state and gets words. */
export function PaceBadge({ row }: { row: SubjectPaceRow }) {
  if (row.status === "green") return <Badge tone="success">on track</Badge>;
  if (row.status === "amber") return <Badge tone="warning">{row.weeks_behind}w behind</Badge>;
  if (row.status === "red") return <Badge tone="danger">{row.weeks_behind}w behind</Badge>;
  if (row.status === "unknown") return <StateChip>nothing logged yet</StateChip>;
  if (row.status === "unplanned") return <StateChip>nothing scheduled</StateChip>;
  if (row.status === "unallocated") return <StateChip>no periods/week</StateChip>;
  return <StateChip>no syllabus</StateChip>;
}

/** A slim coverage bar. Neutral when there is nothing to rate — an unplanned
 *  subject has no coverage, which is a state and not a zero (rule 2). */
function CoverageBar({ pct, status }: { pct: number | null; status: string }) {
  const known = pct != null && status !== "unknown";
  const fill = !known ? "bg-muted-foreground/30"
    : pct >= 75 ? "bg-[color:var(--chart-green)]"
    : pct >= 50 ? "bg-[color:var(--chart-amber)]"
    : "bg-[color:var(--chart-red)]";
  return (
    <span className="flex h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <span className={fill} style={{ width: `${known ? Math.min(pct, 100) : 100}%` }} />
    </span>
  );
}

export function SubjectPaceList({
  rows, showTeacher = false, emptyText,
}: {
  rows: SubjectPaceRow[];
  /** D-15 — only the class teacher's view names who teaches each subject. */
  showTeacher?: boolean;
  emptyText: string;
}) {
  if (!rows.length) {
    return <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">{emptyText}</p>;
  }
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li key={r.class_subject_id}
          className="rounded-xl border border-border bg-card p-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold">
              {r.class_label} · {r.subject_name}
            </span>
            {showTeacher && r.teacher_name ? (
              <span className="text-xs text-muted-foreground">{r.teacher_name}</span>
            ) : null}
            <span className="ml-auto"><PaceBadge row={r} /></span>
          </div>

          <div className="mt-2"><CoverageBar pct={r.coverage_pct} status={r.status} /></div>

          <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {/* Both denominators, each naming itself (S-51). */}
            <span>{r.taught_topics} of {r.planned_topics} planned</span>
            <span>{r.taught_topics} of {r.total_topics} in the syllabus</span>
            {r.unestimated_topics ? (
              <StateChip>{r.unestimated_topics} chapters not sized</StateChip>
            ) : null}
            {r.logged_periods === 0 ? <StateChip>no lessons logged</StateChip> : null}
          </div>

          {/* S-41 — on the class teacher's view, why. Four causes, four
              different conversations; only the last is about teaching. */}
          {showTeacher && r.cause_detail ? (
            <p className="mt-2 text-xs text-muted-foreground">{r.cause_detail}</p>
          ) : null}

          {/* S-46 — the reason she opened the screen at all. */}
          {r.next_topic_title ? (
            <Link href={`/plan/week?class_subject_id=${r.class_subject_id}`}
              className="mt-2 inline-flex items-center gap-1.5 text-sm hover:underline">
              <span className="text-muted-foreground">Next:</span>
              <span className="font-medium">{r.next_topic_title}</span>
              {r.next_chapter_title ? (
                <span className="text-muted-foreground">· {r.next_chapter_title}</span>
              ) : null}
              <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
            </Link>
          ) : (
            <p className="mt-2 text-sm text-muted-foreground">
              {r.total_topics ? "Every topic in the portion is taught." : "No syllabus set up yet."}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}
