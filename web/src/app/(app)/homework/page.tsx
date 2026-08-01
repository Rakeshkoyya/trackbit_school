"use client";

// Homework — the teacher's own screen (V1-5, `D-36` / `S-101`).
//
// **Checking homework is a desk activity, not a between-classes tap.** That is
// the whole reason this route exists: it used to live as a "yesterday's
// homework" block at the top of My Day, where a teacher met it while walking
// between rooms with thirty seconds and a phone. `D-36` moved it here and My Day
// keeps only a counted button pointing at it.
//
// Three levels, in the order she needs them:
//   1. **What I've given** — unchecked first, oldest first. That ordering IS the
//      queue; nothing else on the screen decides what to do next.
//   2. **The check sheet** — one tap for "everyone did it", the roster only when
//      somebody didn't (`components/school/homework-check-sheet.tsx`).
//   3. **By student** — the same component the admin's `D-31` drill-down uses,
//      because they ask the identical question.
//
// The rule the screen is built around: **a homework with no check row is
// `not_checked`, and that is never "everyone did it".** A teacher who checks
// nothing must never read as a class with perfect completion — so the queue
// counts unchecked work as *waiting*, never as done.

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BoardSkeleton, Empty, Section, StateChip } from "@/components/insights/shared";
import { HomeworkCheckSheet } from "@/components/school/homework-check-sheet";
import { StudentHomeworkHistory } from "@/components/school/student-homework-history";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/ui/page-header";
import { schoolApi } from "@/lib/school-api";
import type { HomeworkQueueItem } from "@/lib/school-types";
import { cn } from "@/lib/utils";

type Tab = "given" | "students";

function dayLabel(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN",
    { weekday: "short", day: "numeric", month: "short" });
}

function QueueCard({ item }: { item: HomeworkQueueItem }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-semibold">
          {item.class_label}
          {item.subject_name ? ` · ${item.subject_name}` : ""}
        </span>
        {item.student_name ? (
          <StateChip>just for {item.student_name}</StateChip>
        ) : null}
        <span className="ml-auto text-xs text-muted-foreground">
          set {dayLabel(item.date)}
          {item.due_date ? ` · due ${dayLabel(item.due_date)}` : ""}
        </span>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">{item.text}</p>

      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {item.checked ? (
          <>
            <Badge tone="success">checked</Badge>
            {item.missed ? <Badge tone="danger">{item.missed} didn’t</Badge> : null}
            {item.carried ? <Badge tone="neutral">{item.carried} were away</Badge> : null}
            {!item.missed && !item.carried ? (
              <span className="text-xs text-muted-foreground">everyone did it</span>
            ) : null}
          </>
        ) : (
          <>
            {/* Not a failure — a gap in the record. Amber only once the deadline
                has actually passed, so homework set an hour ago is not a sin. */}
            <Badge tone={item.overdue ? "warning" : "neutral"}>
              {item.overdue ? "not checked yet" : "waiting"}
            </Badge>
            {item.days_waiting > 0 ? (
              <span className="text-xs text-muted-foreground">
                {item.days_waiting} {item.days_waiting === 1 ? "day" : "days"} waiting
              </span>
            ) : null}
          </>
        )}
      </div>

      <div className="mt-3">
        {open || !item.checked ? (
          <HomeworkCheckSheet assignmentId={item.assignment_id} onDone={() => setOpen(false)} />
        ) : (
          <button type="button" onClick={() => setOpen(true)}
            className="text-xs text-muted-foreground underline-offset-2 hover:underline">
            Change what was recorded
          </button>
        )}
      </div>
    </div>
  );
}

function HomeworkInner() {
  const [tab, setTab] = useState<Tab>("given");
  const [studentId, setStudentId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["homework-queue"],
    queryFn: () => schoolApi.homeworkQueue({}),
  });
  const { data: students } = useQuery({
    queryKey: ["students", "for-homework"],
    queryFn: () => schoolApi.students({}),
    enabled: tab === "students",
  });

  if (isLoading || !data) {
    return <><PageHeader title="Homework" subtitle="What you've given, and who did it." /><BoardSkeleton /></>;
  }

  const unchecked = data.items.filter((i) => !i.checked);
  const checked = data.items.filter((i) => i.checked);

  return (
    <div>
      <PageHeader title="Homework" subtitle="What you've given, and who did it." />

      {/* Lead with a sentence, and let the count carry its own meaning: work
          waiting to be checked is the teacher's queue, not a score. */}
      <p className="mb-4 text-base font-medium">
        {data.to_check === 0
          ? "Everything you've set has been gone through."
          : `${data.to_check} ${data.to_check === 1 ? "homework" : "homeworks"} to check`}
        {data.overdue ? ` · ${data.overdue} past the deadline.` : "."}
      </p>

      <div className="mb-5 flex gap-1 rounded-lg border border-border p-0.5">
        {([["given", "What I've given"], ["students", "By student"]] as [Tab, string][]).map(
          ([key, label]) => (
            <button key={key} type="button" onClick={() => setTab(key)}
              className={cn("rounded-md px-3 py-1.5 text-xs font-medium transition-colors",
                tab === key ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground")}>
              {label}
            </button>
          ))}
      </div>

      {tab === "given" ? (
        <>
          <Section title="To check"
            hint="Unchecked first, oldest first. Nothing here expires — late is a status you set, not a deadline that passes.">
            {unchecked.length ? (
              <div className="space-y-2">
                {unchecked.map((i) => <QueueCard key={i.assignment_id} item={i} />)}
              </div>
            ) : (
              <Empty>Nothing waiting. Everything you&apos;ve set has been gone through.</Empty>
            )}
          </Section>

          <Section title="Already checked" hint="Reopen any of these to correct what was recorded.">
            {checked.length ? (
              <div className="space-y-2">
                {checked.map((i) => <QueueCard key={i.assignment_id} item={i} />)}
              </div>
            ) : (
              <Empty>Nothing checked in this window yet.</Empty>
            )}
          </Section>
        </>
      ) : (
        <Section title="By student" hint="Pick a child to see their whole homework record.">
          <div className="mb-3 flex flex-wrap gap-1.5">
            {(students ?? []).slice(0, 60).map((s) => (
              <button key={s.id} type="button" onClick={() => setStudentId(s.id)}
                className={cn("rounded-full border px-3 py-1 text-sm",
                  s.id === studentId ? "border-primary bg-primary/10 font-medium" : "border-border")}>
                {s.full_name}
              </button>
            ))}
          </div>
          {studentId ? (
            <StudentHomeworkHistory studentId={studentId} showName />
          ) : (
            <Empty>Pick a student above.</Empty>
          )}
        </Section>
      )}
    </div>
  );
}

export default function HomeworkPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <HomeworkInner />
    </AuthGuard>
  );
}
