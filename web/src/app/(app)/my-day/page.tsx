"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, ChevronRight, ClipboardCheck, Moon, Send, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { HomeworkPending, MyDayClass, MyDayPeriod } from "@/lib/school-types";

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
            ) : (
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

function HomeworkCheckRow({ hw }: { hw: HomeworkPending }) {
  const qc = useQueryClient();
  const [done, setDone] = useState("");
  const [total, setTotal] = useState("");
  const check = useMutation({
    mutationFn: () => schoolApi.checkHomework(hw.assignment_id, { done_count: Number(done), total_count: Number(total) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["my-day"] }); toast.success("Recorded"); },
    onError: (e) => showApiError(e, "Could not record"),
  });
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <p className="text-sm font-medium">{hw.class_label} · {hw.subject_name}</p>
      <p className="mb-2 truncate text-xs text-muted-foreground">{hw.text}</p>
      <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); if (done && total) check.mutate(); }}>
        <Input className="h-8 w-16" type="number" placeholder="done" value={done} onChange={(e) => setDone(e.target.value)} />
        <span className="text-muted-foreground">/</span>
        <Input className="h-8 w-16" type="number" placeholder="total" value={total} onChange={(e) => setTotal(e.target.value)} />
        <Button size="sm" type="submit" disabled={check.isPending || !done || !total}>Save</Button>
      </form>
    </div>
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

  // Classes already covered by a period row don't need a second card below.
  const periodCsIds = new Set((data?.periods ?? []).map((p) => p.class_subject_id));
  const otherClasses = (data?.classes ?? []).filter((c) => !periodCsIds.has(c.class_subject_id));

  return (
    <div>
      <div className="mb-6">
        <PageHeader title="My Day" subtitle="Tap a period to take attendance, log the topic and set homework" />
      </div>

      {data && data.homework_pending.length > 0 ? (
        <section className="mb-6">
          <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
            <ClipboardCheck className="h-4 w-4" /> Yesterday’s homework — mark completion
          </h2>
          <div className="space-y-2">
            {data.homework_pending.map((hw) => <HomeworkCheckRow key={hw.assignment_id} hw={hw} />)}
          </div>
        </section>
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
