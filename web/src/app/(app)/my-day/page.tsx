"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, ChevronRight, ClipboardCheck, Link2, ListTodo, Moon, Send, Users } from "lucide-react";
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
import { captureFor, timeRange } from "@/lib/day-shape";
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

/** One tappable row per period — every action lives on the period page.
 *
 *  TT-2: a **block** (homework class, games, an extra course, assembly) routes
 *  to its own capture screen and carries none of a subject period's chrome —
 *  no topic, no lesson log, no homework chip, and no attendance count, because
 *  its roll is its own and is taken over there.
 */
function PeriodRow({ p }: { p: MyDayPeriod }) {
  const isBlock = p.slot_type === "block";
  // TT-4 — one row per MEETING. Two classes taught together are one lesson, and
  // every count on this row is the whole room's.
  const combined = (p.combined_class_ids?.length ?? 0) > 1;
  // Once a day (founder, 2026-08-11): the register is the DAY's, so a period
  // that is not being asked for one is not an unfinished period. Reading `done`
  // as "attendance_marked && logged" left every afternoon period grey in a
  // once-per-day school however completely its teacher had captured it — the
  // roll it was waiting on had been taken at nine o'clock by somebody else.
  const attendanceSettled = p.attendance_marked || p.marks_attendance === false;
  const done = attendanceSettled && p.logged;
  // The day's roll is done and this is not the period holding it: say so, in
  // the off state. Nothing to tap, and the silence it replaces read as "this
  // period does not do attendance" — a different fact.
  const rollTakenElsewhere = p.day_attendance_taken === true && !p.attendance_marked;
  const clock = timeRange(p.start, p.end);
  const href = isBlock && p.session_id
    ? `/my-day/block/${p.session_id}`
    : `/my-day/period/${p.class_id}/${p.period_no}`;
  return (
    <Link href={href}
      className="flex items-center gap-3 rounded-xl border border-border bg-card px-4 py-3 transition-colors hover:bg-muted/40 active:scale-[0.995]">
      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-md text-xs font-bold ${
        isBlock ? "bg-primary/10 text-primary"
          : done ? "bg-[color:var(--success,#234a37)]/10 text-[color:var(--success,#234a37)]" : "bg-muted"}`}>
        P{p.period_no}
      </span>
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-1 truncate text-sm font-semibold">
          {/* TT-4: `class_label` IS the room — "5-A + 6-A" — because that is what
              she is walking into. The link mark says it is deliberate, not a
              rendering accident. */}
          {combined ? <Link2 className="h-3.5 w-3.5 shrink-0 text-primary" aria-hidden /> : null}
          <span className="min-w-0 truncate">
            {isBlock
              ? `${p.block_name ?? "Block"} · ${p.class_label}`
              : `${p.class_label}${p.subject_name ? ` · ${p.subject_name}` : ""}`}
          </span>
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {clock ? <span className="tabular-nums">{clock}</span> : null}
          {clock ? " · " : ""}
          {combined && !isBlock ? `${p.combined_class_ids.length} classes together · ` : ""}
          {isBlock
            ? p.block_kind_label ?? captureFor(p.block_kind).label
            : p.status === "not_held" ? "Not held"
              : p.planned_topic ?? "No topic planned this week"}
        </p>
      </div>
      {isBlock ? (
        <div className="flex shrink-0 items-center gap-1.5">
          <Badge tone="primary">{captureFor(p.block_kind).hint}</Badge>
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        </div>
      ) : (
      <div className="flex shrink-0 items-center gap-1.5">
        {p.status === "not_held" ? (
          <Badge tone="neutral">not held</Badge>
        ) : (
          <>
            {p.attendance_marked ? (
              <Badge tone={p.absent_count ? "warning" : "success"}>
                <Users className="h-3 w-3" /> {p.present_count}/{p.roster_count}
              </Badge>
            ) : rollTakenElsewhere ? (
              /* Taken already, elsewhere in the day. Off, not absent from the
                 row: a teacher who sees nothing cannot tell "done" from
                 "this period never marks", and only one of those means she can
                 stop thinking about it. */
              <span className="inline-flex items-center gap-1 rounded-md bg-muted/60 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide text-muted-foreground/70">
                <Check className="h-3 w-3" /> roll taken
              </span>
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
      )}
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

  // The what's-on strip is deliberately GONE from My Day (founder, 2026-08-05).
  // It showed a teacher the whole school — the office's exam block, a
  // colleague's birthday, another class's children — on the one screen she opens
  // between rooms. What she actually needs is her own class's birthdays, and she
  // gets them where they are useful: on the period she is about to log and
  // across My Class (`DayNotice`, scoped to the class).

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

      {/* S-145 — the school locked today, so there is nothing to capture and
          she is told why rather than shown eight rows saying "not logged".
          What was already recorded is untouched (Q-65); it simply stops being
          asked for. */}
      {data?.day_closed ? (
        <div className="mb-6 rounded-xl border border-border bg-muted/40 px-4 py-3 text-sm">
          <span className="font-medium">School is closed today</span>
          {data.lock_reason ? (
            <span className="text-muted-foreground"> · {data.lock_reason}</span>
          ) : null}
          <p className="mt-0.5 text-xs text-muted-foreground">
            Nothing to mark or log. Enjoy it.
          </p>
        </div>
      ) : data?.locked_periods?.length ? (
        <p className="mb-4 text-xs text-muted-foreground">
          {data.lock_reason ? `${data.lock_reason} — ` : ""}
          period{data.locked_periods.length > 1 ? "s" : ""}{" "}
          {data.locked_periods.join(", ")} {data.locked_periods.length > 1 ? "are" : "is"} off
          today.
        </p>
      ) : null}

      {data && data.periods.length > 0 ? (
        <section className="mb-6">
          <h2 className="mb-2 text-sm font-semibold">Today’s periods</h2>
          <div className="space-y-2">
            {data.periods.map((p) => (
              <PeriodRow key={`${p.period_no}-${p.class_subject_id ?? p.session_id ?? p.class_id}`} p={p} />
            ))}
          </div>
        </section>
      ) : null}

      {/* D-41: below the periods, never above them (D-24). */}
      {data ? <TasksSection tasks={data.tasks ?? []} olderCount={data.older_task_count ?? 0} /> : null}

      {!data || (!data.day_closed && data.periods.length === 0 && otherClasses.length === 0) ? (
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
