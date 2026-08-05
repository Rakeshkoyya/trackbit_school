"use client";

/**
 * ABC bands → My students (founder 2026-08-05).
 *
 * Replaces the grouped card list. Three things it does that the list could not:
 *
 *   · **assigned only, and it SAYS when there are none.** A teacher with nobody
 *     assigned used to get a heading over white space, which reads as a broken
 *     screen rather than as an answer.
 *   · **pick a class.** A warden with children in four classes was scrolling
 *     four subject groups to find the two she is about to see.
 *   · **the two actions are on the row.** Her assigned work for a child, and her
 *     log about him — the two things she opens this screen to do — used to be
 *     two navigations away, at the bottom of his support page.
 *
 * The unit is the **placement, not the child** (`D-75`): a boy who is C in Hindi
 * and C in Maths is two rows, because ownership is per subject and collapsing
 * him to one would quietly reinstate the overall letter the module retired. The
 * caption says so, rather than leaving a reader to notice a repeated name.
 *
 * Deliberately absent, and all four are fences rather than omissions (`S-170`):
 * other owners' children · a completion percentage for her check-ins · any
 * comparison of her against another owner · a streak. A finished week must read
 * as finished and an unfinished one must not read as a failing grade.
 */

import { useQuery } from "@tanstack/react-query";
import { ClipboardList, MessageSquarePlus, NotebookPen } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { BandChip } from "@/components/school/band-chip";
import { StudentLogDialog } from "@/components/school/student-log-dialog";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/page-loading";
import { ColumnHead, Empty, Section } from "@/components/insights/shared";
import { schoolApi } from "@/lib/school-api";
import type { MyStudentRow } from "@/lib/school-types";
import { cn } from "@/lib/utils";

function Row({
  r, onLog,
}: {
  r: MyStudentRow;
  onLog: (r: MyStudentRow) => void;
}) {
  const overdue = (r.weeks_since_checkin ?? 99) >= 3;
  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 border-t border-border px-3 py-2.5 first:border-t-0 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto_auto]">
      <div className="min-w-0">
        <Link
          href={`/support/${r.intervention_id}`}
          className="text-sm font-medium hover:underline"
        >
          {r.full_name}
        </Link>
        <p className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          {r.class_label ? <span>{r.class_label}</span> : null}
          {/* "6-A · 1" reads as a stray number; the roll wants its own word. */}
          {r.roll_no ? <span>· roll {r.roll_no}</span> : null}
          <BandChip tier={r.tier} descriptor={r.descriptor} />
          {r.subject_name ? <span>{r.subject_name}</span> : null}
        </p>
      </div>

      <div className="text-xs text-muted-foreground sm:text-right">
        {r.checkins
          ? `${r.checkins} check-in${r.checkins === 1 ? "" : "s"}`
          : "no check-in yet"}
        {overdue && r.weeks_since_checkin != null ? (
          <span className="block text-warning">
            nothing for {r.weeks_since_checkin} weeks
          </span>
        ) : r.checked_in_this_week ? (
          <span className="block text-success">checked in this week</span>
        ) : null}
      </div>

      <div className="flex items-center gap-1.5">
        {r.ready_to_retest ? <Badge tone="success">ready to re-test</Badge> : null}
        {r.open_assignments ? (
          // HW-1's rule: this is the TEACHER's gap. "unchecked" — never "not
          // done", which would be a claim about the child nobody has made.
          <Badge tone="neutral">{r.open_assignments} unchecked</Badge>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        {/* The child's page is where his assigned work is given and checked —
            per-student homework, reused rather than re-invented. */}
        <Link
          href={`/support/${r.intervention_id}`}
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          <NotebookPen className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Assigned work</span>
        </Link>
        <Button size="sm" variant="outline" onClick={() => onLog(r)}>
          <MessageSquarePlus className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">
            Log{r.notes ? ` (${r.notes})` : ""}
          </span>
        </Button>
      </div>
    </div>
  );
}

export function BandMyStudents() {
  const [classId, setClassId] = useState<string | undefined>(undefined);
  const [logging, setLogging] = useState<MyStudentRow | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["band-my-students", classId ?? "all"],
    queryFn: () => schoolApi.myBandStudents(classId),
  });

  if (isLoading || !data) return <PageLoading label="Loading your students…" />;

  const byClass = new Map<string, MyStudentRow[]>();
  for (const r of data.rows) {
    const key = r.class_label ?? "No class";
    byClass.set(key, [...(byClass.get(key) ?? []), r]);
  }

  return (
    <>
      <p className="rounded-xl border border-border bg-card p-4 text-sm leading-relaxed">
        {data.headline}
      </p>

      {/* The picker is built from the classes she actually has children in — a
          dropdown of twelve where eleven are empty is a dropdown nobody uses.
          "All classes" always stays, so a filter can never trap her. */}
      {data.classes.length > 1 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setClassId(undefined)}
            className={cn(
              "rounded-full border px-3 py-1 text-xs transition-colors",
              classId === undefined
                ? "border-primary bg-primary/10 font-medium text-primary"
                : "border-border hover:bg-muted/50",
            )}
          >
            All classes <span className="text-muted-foreground">{data.total}</span>
          </button>
          {data.classes.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setClassId(c.id)}
              className={cn(
                "rounded-full border px-3 py-1 text-xs transition-colors",
                classId === c.id
                  ? "border-primary bg-primary/10 font-medium text-primary"
                  : "border-border hover:bg-muted/50",
              )}
            >
              {c.label} <span className="text-muted-foreground">{c.count}</span>
            </button>
          ))}
        </div>
      ) : null}

      <div className="mt-4">
        {data.rows.length ? (
          <>
            {[...byClass.entries()].map(([label, rows]) => (
              <Section key={label} title={label} className="mb-4">
                <div className="rounded-xl border border-border bg-card">
                  <div className="border-b border-border px-3 py-2">
                    <ColumnHead count={rows.length}>Assigned to you</ColumnHead>
                  </div>
                  {rows.map((r) => (
                    <Row key={r.intervention_id} r={r} onLog={setLogging} />
                  ))}
                </div>
              </Section>
            ))}
            {/* Said once, at the foot: the same child can legitimately appear
                twice, and a reader who notices should find the reason here
                rather than assume a bug. */}
            <p className="text-xs text-muted-foreground">
              One row per subject you own him for — a child supported in two subjects
              appears twice, because the work and the goal are different in each.
            </p>
          </>
        ) : (
          <Empty>
            <span className="flex flex-col items-center gap-2">
              <ClipboardList className="h-5 w-5" />
              {data.total
                ? "Nobody assigned to you in that class — try another."
                : "No students are assigned to you yet. An admin assigns them once a class has been banded."}
            </span>
          </Empty>
        )}
      </div>

      {/* The only place the work pays off — a list that only ever grows is a
          list nobody opens. */}
      {data.moved_on.length ? (
        <Section title="Moved on" hint="Goals met or plans closed." className="mt-6">
          <div className="rounded-xl border border-border bg-card">
            {data.moved_on.map((r) => (
              <div
                key={r.intervention_id}
                className="flex items-center gap-3 border-t border-border px-3 py-2.5 text-sm first:border-t-0"
              >
                <span className="min-w-0 flex-1">
                  {r.full_name}
                  <span className="ml-2 text-xs text-muted-foreground">
                    {r.subject_name} · {r.status === "achieved" ? "moved up" : "closed"}
                  </span>
                </span>
                <Badge tone="success">done</Badge>
              </div>
            ))}
          </div>
        </Section>
      ) : null}

      {logging ? (
        <StudentLogDialog
          open
          onOpenChange={(v) => !v && setLogging(null)}
          studentId={logging.student_id}
          studentName={logging.full_name}
        />
      ) : null}
    </>
  );
}
