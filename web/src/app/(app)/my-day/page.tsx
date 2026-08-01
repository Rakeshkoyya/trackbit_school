"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, ChevronRight, ClipboardCheck, ListTodo, Moon, Send, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { OutcomeSheet } from "@/components/tasks/outcome-sheet";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { appApi } from "@/lib/app-api";
import { showApiError } from "@/lib/errors";
import { dayLabel } from "@/lib/format";
import { schoolApi } from "@/lib/school-api";
import type { MyDayClass, MyDayPeriod } from "@/lib/school-types";
import type { Task } from "@/lib/types";

type HwTarget = { csId: string; title: string };

function HomeworkSheet({ target, onClose }: { target: HwTarget | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [due, setDue] = useState("");
  const add = useMutation({
    mutationFn: () => schoolApi.addHomework({
      class_subject_id: target!.csId, text: text.trim(), due_date: due || null,
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["my-day"] });
      toast.success(`Homework set · ${res.notified_count} parents notified`);
      setText(""); setDue(""); onClose();
    },
    onError: (e) => showApiError(e, "Could not set homework"),
  });
  return (
    <Sheet open={!!target} onOpenChange={(v) => { if (!v) onClose(); }} title={target ? `Homework · ${target.title}` : ""}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) add.mutate(); }}>
        <Input autoFocus placeholder="e.g. Draw the water cycle" value={text} onChange={(e) => setText(e.target.value)} />
        <div><label className="text-xs text-muted-foreground">Due (optional)</label><Input type="date" value={due} onChange={(e) => setDue(e.target.value)} /></div>
        <Button type="submit" className="w-full" disabled={add.isPending || !text.trim()}>
          <Send className="h-4 w-4" /> {add.isPending ? "Sending…" : "Set homework & notify parents"}
        </Button>
      </form>
    </Sheet>
  );
}

/** One tappable row per period — every action lives on the period page. */
function PeriodRow({ p }: { p: MyDayPeriod }) {
  const done = p.attendance_marked && p.logged;
  return (
    <Link href={`/my-day/period/${p.class_id}/${p.period_no}`}
      className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 transition-colors hover:bg-muted/40 active:scale-[0.995]">
      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-md text-xs font-bold ${done ? "bg-[color:var(--success,#234a37)]/10 text-[color:var(--success,#234a37)]" : "bg-muted"}`}>
        P{p.period_no}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold">
          {p.class_label}{p.subject_name ? ` · ${p.subject_name}` : ""}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {p.status === "not_held" ? "Not held" : p.planned_topic ?? "No topic planned this week"}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        {p.status === "not_held" ? (
          <Badge tone="neutral">not held</Badge>
        ) : (
          <>
            {p.attendance_marked ? (
              <Badge tone={p.absent_count ? "warning" : "success"}>
                <Users className="h-3 w-3" /> {p.present_count}/{p.roster_count}
              </Badge>
            ) : p.marks_attendance === false ? null : (
              /* V1-3 (D-01): a period this school's mode never marks shows no
                 attendance chip at all — an empty one would read as a chore. */
              <Badge tone="neutral"><Users className="h-3 w-3" /> —</Badge>
            )}
            {p.logged ? <Badge tone="success"><Check className="h-3 w-3" /> topic</Badge> : null}
            {p.homework_set ? <Badge tone="primary"><BookOpen className="h-3 w-3" /> hw</Badge> : null}
          </>
        )}
        <ChevronRight className="h-4 w-4 text-muted-foreground" />
      </div>
    </Link>
  );
}

/** Classes with no timetabled period today — quick log stays inline. */
function ClassCard({ c, onHomework }: { c: MyDayClass; onHomework: () => void }) {
  const qc = useQueryClient();
  const log = useMutation({
    mutationFn: (coverage: string) => schoolApi.logLesson({ class_subject_id: c.class_subject_id, topic_id: c.planned_topic_id, coverage }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["my-day"] }); toast.success("Logged"); },
    onError: (e) => showApiError(e, "Could not log"),
  });
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <p className="text-sm font-semibold">{c.class_label} · {c.subject_name}</p>
          <p className="text-xs text-muted-foreground">
            {c.planned_topic ? `Planned: ${c.planned_topic}` : "No topic planned this week"}
          </p>
        </div>
        {c.logged ? <Badge tone="success"><Check className="h-3 w-3" /> Logged</Badge> : <Badge tone="neutral">Not logged</Badge>}
      </div>
      <div className="flex flex-wrap gap-2">
        {!c.logged ? (
          <>
            <Button size="sm" onClick={() => log.mutate("full")} disabled={log.isPending}>Covered</Button>
            <Button size="sm" variant="outline" onClick={() => log.mutate("partial")} disabled={log.isPending}>Partially</Button>
          </>
        ) : null}
        <Button size="sm" variant={c.homework_set ? "outline" : "ghost"} onClick={onHomework}>
          <BookOpen className="h-4 w-4" /> {c.homework_set ? "Homework set" : "Set homework"}
        </Button>
      </div>
    </div>
  );
}

/** D-41/D-43: the narrow task window under the periods — rail follow-ups from
 *  the last 3 working days plus anything due today, tickable in place. My Day
 *  is a prompt, not an inbox: everything else lives on /tasks, and the footer
 *  count says so ("4 older tasks →"). */
function TasksSection({ tasks, olderCount }: { tasks: Task[]; olderCount: number }) {
  const qc = useQueryClient();
  const [outcomeFor, setOutcomeFor] = useState<Task | null>(null);

  const complete = useMutation({
    mutationFn: ({ task, outcome }: { task: Task; outcome: string | null }) =>
      appApi.completeTask(task.id, outcome),
    onSuccess: () => {
      toast.success("Done ✓");
      qc.invalidateQueries({ queryKey: ["my-day"] });
      qc.invalidateQueries({ queryKey: ["my-tasks"] });
    },
    onError: (e) => showApiError(e, "Could not complete"),
  });
  // D-46: a follow-up about a person asks "what happened?"; the rest are one tap.
  const tick = (task: Task) => {
    if (task.subject) setOutcomeFor(task);
    else complete.mutate({ task, outcome: null });
  };

  if (tasks.length === 0 && olderCount === 0) return null;
  const now = new Date();
  return (
    <section className="mt-6">
      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        <ListTodo className="h-4 w-4" /> Tasks
      </h2>
      <div className="space-y-2">
        {tasks.map((t) => {
          const overdue = t.due_at != null && new Date(t.due_at) < now;
          const dueLabel = t.due_at ? dayLabel(t.due_at) : null;
          return (
            <div key={t.id}
              className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3">
              <button
                onClick={() => tick(t)}
                disabled={complete.isPending}
                aria-label="Mark done"
                className="h-6 w-6 shrink-0 rounded-full border-2 border-muted-foreground/30 transition-colors hover:border-success hover:bg-success/10"
              />
              <Link href={`/task/${t.id}`} className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium">{t.title}</p>
                <p className="truncate text-xs text-muted-foreground">
                  {t.board_name}
                  {t.asked_by ? ` · ${t.asked_by} asked` : ""}
                </p>
              </Link>
              {dueLabel ? (
                <Badge tone={overdue ? "danger" : "neutral"}>
                  {overdue ? `due ${dueLabel.toLowerCase()}` : dueLabel}
                </Badge>
              ) : null}
            </div>
          );
        })}
      </div>
      {olderCount > 0 ? (
        <Link href="/tasks"
          className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline">
          {olderCount} older task{olderCount === 1 ? "" : "s"} <ChevronRight className="h-3 w-3" />
        </Link>
      ) : null}
      <OutcomeSheet
        target={outcomeFor ? { title: outcomeFor.title, subjectName: outcomeFor.subject?.name } : null}
        onClose={() => setOutcomeFor(null)}
        onConfirm={(outcome) => {
          if (outcomeFor) complete.mutate({ task: outcomeFor, outcome });
          setOutcomeFor(null);
        }}
      />
    </section>
  );
}

/** This evening (HS): the teacher's hostel blocks for today, from the sessions list. */
function EveningSection() {
  const { data: sessions = [] } = useQuery({ queryKey: ["sessions"], queryFn: schoolApi.sessions });
  const today = (new Date().getDay() + 6) % 7; // JS Sunday=0 → Python Mon=0
  const mine = sessions
    .filter((s) => s.active && s.weekdays.includes(today))
    .sort((a, b) => (a.time ?? "").localeCompare(b.time ?? ""));
  if (mine.length === 0) return null;
  return (
    <section className="mt-6">
      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        <Moon className="h-4 w-4" /> This evening
      </h2>
      <div className="space-y-2">
        {mine.map((s) => (
          <Link key={s.id} href={`/sessions/${s.id}`}
            className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 transition-colors hover:bg-muted/40 active:scale-[0.995]">
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold">{s.name}</p>
              <p className="truncate text-xs text-muted-foreground">
                {s.time}{s.end_time ? `–${s.end_time}` : ""}
                {s.class_labels.length > 0 ? ` · ${s.class_labels.join(", ")}` : ""} · {s.roster_count} students
              </p>
            </div>
            <Badge tone={s.kind === "activity" ? "success" : s.kind === "homework" ? "warning" : "primary"}>{s.kind}</Badge>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          </Link>
        ))}
      </div>
    </section>
  );
}

function MyDayInner() {
  const [hwFor, setHwFor] = useState<HwTarget | null>(null);
  const { data } = useQuery({ queryKey: ["my-day"], queryFn: schoolApi.myDay });

  // S-100: the count that makes the button worth pressing. Its own query so a
  // slow analytics read never delays the periods, which are the point of My Day.
  const { data: queue } = useQuery({
    queryKey: ["homework-queue"],
    queryFn: () => schoolApi.homeworkQueue({}),
  });
  const toCheck = queue?.to_check ?? 0;
  const overdue = queue?.overdue ?? 0;

  // Classes already covered by a period row don't need a second card below.
  const periodCsIds = new Set((data?.periods ?? []).map((p) => p.class_subject_id));
  const otherClasses = (data?.classes ?? []).filter((c) => !periodCsIds.has(c.class_subject_id));

  return (
    <div>
      <div className="mb-6">
        <PageHeader title="My Day" subtitle="Tap a period to take attendance, log the topic and set homework" />
      </div>

      {/* S-100 / D-36 — a counted button, not a block of sheets.
          Checking homework is a DESK activity: the old "yesterday's homework"
          section met a teacher here, walking between rooms with thirty seconds
          and a phone, and asked her to go through thirty names. It now lives on
          /homework and this is the pointer. Recorded so nobody optimises it back. */}
      {toCheck > 0 ? (
        <Link href="/homework"
          className="mb-6 flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 hover:bg-accent">
          <ClipboardCheck className="h-4 w-4 shrink-0" />
          <span className="min-w-0 flex-1 text-sm font-medium">
            Homework · {toCheck} to check
          </span>
          {overdue > 0 ? <Badge tone="warning">{overdue} past due</Badge> : null}
        </Link>
      ) : null}

      {data && data.periods.length > 0 ? (
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold">Today’s periods</h2>
          <div className="space-y-2">
            {data.periods.map((p) => (
              <PeriodRow key={`${p.period_no}-${p.class_subject_id}`} p={p} />
            ))}
          </div>
        </section>
      ) : null}

      {/* D-41: below the periods, never above them (D-24). */}
      {data ? <TasksSection tasks={data.tasks ?? []} olderCount={data.older_task_count ?? 0} /> : null}

      {!data || (data.periods.length === 0 && otherClasses.length === 0) ? (
        data && data.homework_pending.length === 0 ? (
          <EmptyState icon={BookOpen} title="No classes assigned to you"
            body="Ask your admin to assign your subjects on the Setup → class page." />
        ) : null
      ) : otherClasses.length > 0 ? (
        <section>
          <h2 className="mb-2 text-sm font-semibold">
            {data && data.periods.length > 0 ? "Not on today’s timetable" : "Today’s classes"}
          </h2>
          <div className="space-y-3">
            {otherClasses.map((c) => (
              <ClassCard key={c.class_subject_id} c={c}
                onHomework={() => setHwFor({ csId: c.class_subject_id, title: `${c.class_label} ${c.subject_name}` })} />
            ))}
          </div>
        </section>
      ) : null}

      <EveningSection />

      <HomeworkSheet target={hwFor} onClose={() => setHwFor(null)} />
    </div>
  );
}

export default function ClassroomPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MyDayInner />
    </AuthGuard>
  );
}
