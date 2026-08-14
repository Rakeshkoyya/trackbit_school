"use client";

// The period page — everything a teacher does for one class-period, opened from
// a My Day row. Attendance + topic are the core loop; homework, checks and the
// deep log (sections → concepts → tapped students) are optional extras (P1v2).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, BookOpen, Camera, Check, ChevronDown, ChevronRight, Link2, ListChecks,
  Plus, Send, UserCheck, Users, X,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ClassDayNotice } from "@/components/school/day-notice";
import { CaptureReview, useStartCapture } from "@/components/school/score-capture";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { DailyCheck, ObservationSection, PeriodCard, PeriodPlan } from "@/lib/school-types";

function Section({ title, icon, children, aside }: {
  title: string; icon: React.ReactNode; children: React.ReactNode; aside?: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">{icon} {title}</h2>
        {aside}
      </div>
      {children}
    </section>
  );
}

// ── 1 · attendance — a tappable row that opens the roll-call page ────────────
/** TT-4: on a combined period the counts are the ROOM's, summed from each
 *  class's own register, and "marked" is ALL of them. A half-marked room shown
 *  as done would lose a class's day quietly. */
function roomCounts(card: PeriodCard) {
  const parts = card.combined ?? [];
  if (parts.length < 2) {
    return {
      marked: card.attendance_marked, roster: card.roster_count,
      present: card.present_count, absent: card.absent_count, late: card.late_count,
    };
  }
  const marked = parts.every((c) => c.attendance_marked);
  const sum = (pick: (c: (typeof parts)[number]) => number | null) =>
    parts.reduce((n, c) => n + (pick(c) ?? 0), 0);
  return {
    marked,
    roster: sum((c) => c.roster_count),
    present: marked ? sum((c) => c.present_count) : null,
    absent: marked ? sum((c) => c.absent_count) : null,
    late: marked ? sum((c) => c.late_count) : null,
  };
}

function AttendanceSection({ card }: { card: PeriodCard }) {
  const room = roomCounts(card);
  // Founder, 2026-08-05 — once a day means once a day. In a school on
  // `first_period` the register belongs to the DAY, so a period that is not
  // asking is not asking for one of two very different reasons, and the teacher
  // cares which:
  //
  //   · `day_attendance_taken` — somebody already took it this morning. Say so,
  //     and get out of the way. This is the noise the founder asked to remove:
  //     six teachers being asked about a roll that was called at 9am.
  //   · otherwise — this period simply is not a marking slot for the school's
  //     mode. Still openable, in case she needs to record something anyway.
  if (!card.marks_attendance && !card.attendance_marked) {
    if (card.day_attendance_taken) {
      // Not a link. There is nothing to do here, and a tappable row would put
      // the register one mis-tap away from being re-opened by the wrong person.
      return (
        <div className="flex items-center gap-3 rounded-xl border border-border bg-card/60 p-4">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-[color:var(--success,#234a37)]/10 text-[color:var(--success,#234a37)]">
            <UserCheck className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Attendance already taken today</p>
            <p className="truncate text-xs text-muted-foreground">
              Your school takes one register a day, and today&rsquo;s is done.
            </p>
          </div>
        </div>
      );
    }
    return (
      <Link href={`/my-day/period/${card.class_id}/${card.period_no}/attendance`}
        className="flex items-center gap-3 rounded-xl border border-dashed border-border bg-card/60 p-4 text-muted-foreground transition-colors hover:bg-muted/30">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-muted">
          <Users className="h-4 w-4" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">Attendance not taken this period</p>
          <p className="truncate text-xs">
            Your school takes it at fixed times of day. Tap if you need to record it anyway.
          </p>
        </div>
        <ChevronRight className="h-4 w-4" />
      </Link>
    );
  }
  return (
    <Link href={`/my-day/period/${card.class_id}/${card.period_no}/attendance`}
      className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-muted/40 active:scale-[0.995]">
      <span className={`grid h-9 w-9 shrink-0 place-items-center rounded-md ${room.marked ? "bg-[color:var(--success,#234a37)]/10 text-[color:var(--success,#234a37)]" : "bg-muted text-muted-foreground"}`}>
        <Users className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold">
          Attendance
          {card.combined_label ? (
            <span className="ml-1.5 font-normal text-muted-foreground">· {card.combined_label}</span>
          ) : null}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {room.roster === 0 ? "No students on the roster yet"
            : room.marked
              ? card.roster.filter((r) => r.status).map((r) =>
                  `${r.full_name} ${r.status}${r.late_minutes ? ` ${r.late_minutes}m` : ""}`).join(" · ") || "Everyone present"
              : card.combined_label
                ? "One roll call for both classes — tap to take it"
                : "Not taken yet — tap to call the roll"}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        {room.marked ? (
          <>
            <Badge tone={room.absent ? "warning" : "success"}>
              <UserCheck className="h-3 w-3" /> {room.present}/{room.roster}
            </Badge>
            {room.late ? <Badge tone="warning">{room.late} late</Badge> : null}
          </>
        ) : (
          <Badge tone="neutral">take now</Badge>
        )}
        <ChevronRight className="h-4 w-4 text-muted-foreground" />
      </div>
    </Link>
  );
}

// ── 2 · topics — pick from the list and it's saved instantly; delete to undo ─
/** One class's topics for this period.
 *
 *  TT-4: a combined period renders one of these PER CLASS, and that is
 *  deliberate. Everything else about a shared lesson is genuinely one act — one
 *  roll call, one homework — but the syllabus is not: a 5th-class chapter is not
 *  a 6th-class chapter, and a single shared picker would either move the wrong
 *  syllabus or need a seventh definition of "covered" to reconcile them. Two
 *  taps, and both classes' pace figures stay true.
 */
function TopicPicker({ csId, periodNo, plan, onSaved }: {
  csId: string; periodNo: number; plan: PeriodPlan; onSaved: () => void;
}) {
  const log = useMutation({
    mutationFn: (topicId: string) => schoolApi.logLesson({
      class_subject_id: csId, topic_id: topicId, coverage: "full",
      period_no: periodNo,
    }),
    onSuccess: () => { toast.success("Added — taught today"); onSaved(); },
    onError: (e) => showApiError(e, "Could not add"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteLog(id),
    onSuccess: () => { toast.success("Removed"); onSaved(); },
    onError: (e) => showApiError(e, "Could not remove"),
  });

  // Group the syllabus list by chapter; hide topics already added to THIS period.
  const inPeriod = new Set(plan.logged.map((l) => l.topic_id));
  const byUnit = new Map<string, typeof plan.progress>();
  for (const row of plan.progress) {
    if (inPeriod.has(row.topic_id)) continue;
    if (!byUnit.has(row.unit_title)) byUnit.set(row.unit_title, []);
    byUnit.get(row.unit_title)!.push(row);
  }

  return (
    <div>
      {log.isPending ? (
        <p className="mb-1 text-right text-xs text-muted-foreground">saving…</p>
      ) : null}

      {plan.logged.length > 0 ? (
        <ul className="mb-3 space-y-1">
          {plan.logged.map((l) => (
            <li key={l.id} className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm">
              <Check className="h-4 w-4 shrink-0 text-[color:var(--success,#234a37)]" />
              <span className="min-w-0 flex-1 truncate font-medium">{l.topic_title ?? "No specific topic"}</span>
              <Badge tone="success">taught today</Badge>
              <button type="button" aria-label="Remove topic" onClick={() => remove.mutate(l.id)}
                disabled={remove.isPending}
                className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mb-2 text-sm text-muted-foreground">Nothing added yet — pick from the syllabus below.</p>
      )}

      {plan.planned_topic_title && !inPeriod.has(plan.planned_topic_id) ? (
        <button type="button" disabled={log.isPending}
          onClick={() => plan.planned_topic_id && log.mutate(plan.planned_topic_id)}
          className="mb-2 flex w-full items-center gap-2 rounded-lg border border-dashed border-primary/50 px-3 py-2 text-left text-sm hover:bg-accent/50">
          <Plus className="h-4 w-4 shrink-0 text-primary" />
          <span className="min-w-0 flex-1 truncate">
            Planned this week: <span className="font-medium">{plan.planned_topic_title}</span>
            {plan.planned_unit_title ? <span className="text-muted-foreground"> ({plan.planned_unit_title})</span> : null}
          </span>
          <span className="shrink-0 text-xs text-muted-foreground">tap to add</span>
        </button>
      ) : null}

      {plan.progress.length > 0 ? (
        <select
          aria-label="Add a topic from the syllabus"
          className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
          value=""
          disabled={log.isPending}
          onChange={(e) => { if (e.target.value) log.mutate(e.target.value); }}>
          <option value="">+ Add a topic from the syllabus…</option>
          {[...byUnit.entries()].map(([unit, rows]) => (
            <optgroup key={unit} label={unit}>
              {rows.map((r) => (
                <option key={r.topic_id} value={r.topic_id}>
                  {r.topic_title}{r.status === "done" ? " ✓" : r.status === "in_progress" ? " ◐" : ""}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      ) : (
        <p className="text-sm text-muted-foreground">No syllabus loaded for this subject yet.</p>
      )}
      <p className="mt-2 text-xs text-muted-foreground">
        Picking a topic saves it instantly. The same topic can be added again on another day
        if it takes longer than one class.
      </p>
    </div>
  );
}

function TopicSection({ card, onSaved }: { card: PeriodCard; onSaved: () => void }) {
  const combined = card.combined ?? [];
  if (combined.length > 1) {
    return (
      <Section title="Topics taught" icon={<Check className="h-4 w-4" />}>
        <p className="mb-3 text-xs text-muted-foreground">
          One lesson, two syllabuses. Log what each class actually covered — their
          chapters are their own, so their pace stays their own.
        </p>
        <div className="space-y-4">
          {combined.map((c) => (
            <div key={c.class_id} className="rounded-lg border border-border bg-background p-3">
              <p className="mb-2 text-sm font-semibold">
                {c.class_label}
                {c.subject_name ? <span className="font-normal text-muted-foreground"> · {c.subject_name}</span> : null}
              </p>
              {c.class_subject_id ? (
                <TopicPicker csId={c.class_subject_id} periodNo={card.period_no}
                  plan={c.plan} onSaved={onSaved} />
              ) : (
                <p className="text-sm text-muted-foreground">No subject timetabled for this class.</p>
              )}
            </div>
          ))}
        </div>
      </Section>
    );
  }
  return (
    <Section title="Topics taught" icon={<Check className="h-4 w-4" />}>
      {card.class_subject_id == null ? (
        <p className="text-sm text-muted-foreground">No subject is timetabled for this period.</p>
      ) : (
        <TopicPicker csId={card.class_subject_id} periodNo={card.period_no}
          plan={card.plan} onSaved={onSaved} />
      )}
    </Section>
  );
}

// ── 3 · homework — class-wide or per-student ─────────────────────────────────
function HomeworkSection({ card, onSaved }: { card: PeriodCard; onSaved: () => void }) {
  const [text, setText] = useState("");
  const [due, setDue] = useState("");
  const [studentId, setStudentId] = useState("");
  const [adding, setAdding] = useState(false);
  // TT-4 — the same homework, set once for the room. Every class starts ticked
  // because that is what a combined lesson usually means; untick one and it
  // simply doesn't get it. A note for a NAMED child never fans out — those
  // children are all in one class, and copying it would message a stranger's
  // parents (the server enforces this too).
  const others = (card.combined ?? []).filter(
    (c) => c.class_subject_id && c.class_subject_id !== card.class_subject_id);
  const [alsoFor, setAlsoFor] = useState<Set<string>>(new Set());
  const [seededFor, setSeededFor] = useState<string | null>(null);
  const othersKey = others.map((c) => c.class_subject_id).join(",");
  if (othersKey !== seededFor) {
    setSeededFor(othersKey);
    setAlsoFor(new Set(others.map((c) => c.class_subject_id!)));
  }

  const nameOf = new Map(card.roster.map((r) => [r.student_id, r.full_name]));
  const add = useMutation({
    mutationFn: () => schoolApi.addHomework({
      class_subject_id: card.class_subject_id!, text: text.trim(),
      due_date: due || null, student_id: studentId || null,
      also_class_subject_ids: studentId ? [] : [...alsoFor],
    }),
    onSuccess: (res) => {
      toast.success(`Homework set · ${res.notified_count} parents notified`);
      setText(""); setDue(""); setStudentId(""); setAdding(false);
      onSaved();
    },
    onError: (e) => showApiError(e, "Could not set homework"),
  });

  if (card.class_subject_id == null) return null;
  return (
    <Section title="Homework" icon={<BookOpen className="h-4 w-4" />}
      aside={!adding ? (
        <Button size="sm" variant="ghost" onClick={() => setAdding(true)}><Plus className="h-4 w-4" /> Add</Button>
      ) : null}>
      {card.homework.length === 0 && !adding ? (
        <p className="text-sm text-muted-foreground">None set today — homework is optional.</p>
      ) : (
        <ul className="space-y-1 text-sm">
          {card.homework.map((h) => (
            <li key={h.id} className="flex items-start gap-2">
              <span className="min-w-0 flex-1">{h.text}</span>
              {h.student_id ? <Badge tone="primary">{nameOf.get(h.student_id) ?? "1 student"}</Badge> : null}
              {h.due_date ? <span className="shrink-0 text-xs text-muted-foreground">due {h.due_date}</span> : null}
            </li>
          ))}
        </ul>
      )}
      {adding ? (
        <form className="mt-3 space-y-2 border-t border-border pt-3"
          onSubmit={(e) => { e.preventDefault(); if (text.trim()) add.mutate(); }}>
          <Input autoFocus placeholder="e.g. Draw the water cycle" value={text} onChange={(e) => setText(e.target.value)} />
          <div className="grid grid-cols-2 gap-2">
            <select aria-label="For" className="h-9 rounded-md border border-border bg-background px-2 text-sm"
              value={studentId} onChange={(e) => setStudentId(e.target.value)}>
              <option value="">Whole class</option>
              {card.roster.map((r) => <option key={r.student_id} value={r.student_id}>{r.full_name}</option>)}
            </select>
            <Input type="date" aria-label="Due date" value={due} onChange={(e) => setDue(e.target.value)} />
          </div>
          {others.length > 0 ? (
            <div className="rounded-md border border-border bg-background px-2 py-1.5">
              <p className="mb-1 text-xs text-muted-foreground">
                {studentId
                  ? "A note for one child goes to that child only."
                  : "Also set it for"}
              </p>
              {!studentId ? (
                <div className="flex flex-wrap gap-1.5">
                  {others.map((c) => {
                    const on = alsoFor.has(c.class_subject_id!);
                    return (
                      <button key={c.class_id} type="button"
                        onClick={() => setAlsoFor((prev) => {
                          const next = new Set(prev);
                          if (on) next.delete(c.class_subject_id!);
                          else next.add(c.class_subject_id!);
                          return next;
                        })}
                        className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                          on ? "border-primary bg-primary text-primary-foreground"
                            : "border-border bg-card hover:bg-muted"}`}>
                        {on ? <Check className="mr-1 inline h-3 w-3" /> : null}{c.class_label}
                      </button>
                    );
                  })}
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="flex gap-2">
            <Button type="submit" className="flex-1" disabled={add.isPending || !text.trim()}>
              <Send className="h-4 w-4" /> {add.isPending ? "Sending…" : "Set & notify parents"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setAdding(false)}>Cancel</Button>
          </div>
        </form>
      ) : null}
    </Section>
  );
}

// ── 4 · today's checks (recommendations) ─────────────────────────────────────
function ChecksSection({ card }: { card: PeriodCard }) {
  const qc = useQueryClient();
  const csId = card.class_subject_id;
  const [flagFor, setFlagFor] = useState<DailyCheck | null>(null);
  const [notDone, setNotDone] = useState<Record<string, true>>({});
  const { data } = useQuery({
    queryKey: ["checks", csId],
    queryFn: () => schoolApi.checks(csId!),
    enabled: !!csId,
  });
  const confirm = useMutation({
    mutationFn: (v: { id: string; exceptions: { student_id: string; status: "not_done" }[] }) =>
      schoolApi.confirmCheck(v.id, v.exceptions),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["checks", csId] });
      setFlagFor(null);
      toast.success("Saved");
    },
    onError: (e) => showApiError(e, "Could not save"),
  });

  if (!csId || !data || data.checks.length === 0) return null;

  const openFlag = (c: DailyCheck) => {
    const initial: Record<string, true> = {};
    for (const r of c.results) if (r.status === "not_done") initial[r.student_id] = true;
    setNotDone(initial);
    setFlagFor(c);
  };

  return (
    <Section title="Today’s checks" icon={<ListChecks className="h-4 w-4" />}>
      <div className="space-y-2">
        {data.checks.map((c) => (
          <div key={c.id}>
            <div className="flex items-start gap-2 text-sm">
              <div className="min-w-0 flex-1">
                <p className="leading-snug">{c.description}</p>
                <div className="mt-0.5 flex flex-wrap items-center gap-1">
                  {c.band_scope !== "all" ? <Badge tone="primary">Band {c.band_scope}</Badge> : null}
                  {c.student_name ? <Badge tone="neutral">{c.student_name}</Badge> : null}
                  {c.confirmed && c.results.length > 0
                    ? <Badge tone="warning">{c.results.length} didn’t do it</Badge> : null}
                </div>
              </div>
              {c.confirmed ? (
                <button type="button" onClick={() => openFlag(c)}
                  className="shrink-0 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted">
                  <Check className="mr-0.5 inline h-3.5 w-3.5 text-[color:var(--success,#234a37)]" />edit
                </button>
              ) : (
                <div className="flex shrink-0 gap-1">
                  <Button size="sm" onClick={() => confirm.mutate({ id: c.id, exceptions: [] })}
                    disabled={confirm.isPending}>Class did it</Button>
                  <Button size="sm" variant="outline" onClick={() => openFlag(c)}>Flag</Button>
                </div>
              )}
            </div>
            {flagFor?.id === c.id ? (
              <div className="mt-2 rounded-lg border border-border bg-background p-2">
                <p className="mb-1 text-xs text-muted-foreground">Tap who didn’t do it</p>
                <div className="mb-2 grid gap-1 sm:grid-cols-2">
                  {card.roster.map((r) => (
                    <button key={r.student_id} type="button"
                      onClick={() => setNotDone((prev) => {
                        const out = { ...prev };
                        if (out[r.student_id]) delete out[r.student_id]; else out[r.student_id] = true;
                        return out;
                      })}
                      className="flex w-full items-center justify-between rounded-md border border-border bg-card px-2 py-1.5 text-left text-sm">
                      <span className="truncate">{r.full_name}</span>
                      {notDone[r.student_id] ? <Badge tone="warning">didn’t</Badge> : <Badge tone="success">did</Badge>}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <Button size="sm" className="flex-1" disabled={confirm.isPending}
                    onClick={() => confirm.mutate({
                      id: c.id,
                      exceptions: Object.keys(notDone).map((student_id) => ({ student_id, status: "not_done" as const })),
                    })}>Save</Button>
                  <Button size="sm" variant="ghost" onClick={() => setFlagFor(null)}>Cancel</Button>
                </div>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </Section>
  );
}

// ── 5 · deep log (optional) — sections → concepts → tapped students ──────────
type Flag = { rating: "needs_work" | "excellent" };
type ConceptDraft = { concept: string; flags: Record<string, Flag> };

function SectionEditor({ card, existing, onClose }: {
  card: PeriodCard; existing: ObservationSection | null; onClose: () => void;
}) {
  const qc = useQueryClient();
  const [name, setName] = useState(existing?.section ?? "");
  const [concepts, setConcepts] = useState<ConceptDraft[]>(() =>
    (existing?.concepts ?? []).filter((c) => c.concept != null).map((c) => ({
      concept: c.concept!,
      flags: Object.fromEntries(c.students.map((s) => [s.student_id, { rating: s.rating }])),
    })));
  const [newConcept, setNewConcept] = useState("");
  const [flagOpen, setFlagOpen] = useState<number | null>(null);

  const save = useMutation({
    mutationFn: () => schoolApi.saveObservationSection({
      class_subject_id: card.class_subject_id!, section: name.trim(),
      period_no: card.period_no,
      concepts: concepts.map((c) => ({
        concept: c.concept,
        students: Object.entries(c.flags).map(([student_id, f]) => ({ student_id, rating: f.rating })),
      })),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["observations", card.class_subject_id] });
      toast.success("Section saved");
      onClose();
    },
    onError: (e) => showApiError(e, "Could not save"),
  });

  // Tap cycles a student none → needs work → excellent → none.
  const cycleFlag = (ci: number, studentId: string) => setConcepts((prev) => prev.map((c, i) => {
    if (i !== ci) return c;
    const flags = { ...c.flags };
    const cur = flags[studentId]?.rating;
    if (cur == null) flags[studentId] = { rating: "needs_work" };
    else if (cur === "needs_work") flags[studentId] = { rating: "excellent" };
    else delete flags[studentId];
    return { ...c, flags };
  }));

  return (
    <div className="mt-3 rounded-lg border border-border bg-background p-3">
      <div className="mb-2 flex items-center gap-2">
        <Input placeholder="Section name, e.g. Vocabulary" value={name}
          onChange={(e) => setName(e.target.value)} disabled={!!existing} />
        <Button variant="ghost" size="sm" onClick={onClose}><X className="h-4 w-4" /></Button>
      </div>

      {concepts.map((c, ci) => (
        <div key={ci} className="mb-2 rounded-md border border-border bg-card p-2">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">{c.concept}</p>
            <div className="flex items-center gap-1">
              <Button size="sm" variant="ghost" onClick={() => setFlagOpen(flagOpen === ci ? null : ci)}>
                Flag students {flagOpen === ci ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              </Button>
              <Button size="sm" variant="ghost"
                onClick={() => setConcepts((prev) => prev.filter((_, i) => i !== ci))}>
                <X className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
          {Object.keys(c.flags).length > 0 ? (
            <div className="mt-1 flex flex-wrap gap-1">
              {Object.entries(c.flags).map(([sid, f]) => (
                <Badge key={sid} tone={f.rating === "needs_work" ? "warning" : "success"}>
                  {card.roster.find((r) => r.student_id === sid)?.full_name ?? "?"} · {f.rating === "needs_work" ? "needs work" : "excellent"}
                </Badge>
              ))}
            </div>
          ) : null}
          {flagOpen === ci ? (
            <div className="mt-2 grid gap-1 sm:grid-cols-2">
              <p className="col-span-full text-xs text-muted-foreground">
                Tap to cycle: fine → needs work → excellent. Untapped = fine.
              </p>
              {card.roster.map((r) => {
                const f = c.flags[r.student_id];
                return (
                  <button key={r.student_id} type="button" onClick={() => cycleFlag(ci, r.student_id)}
                    className="flex w-full items-center justify-between rounded-md border border-border bg-background px-2 py-1.5 text-left text-sm">
                    <span className="truncate">{r.full_name}</span>
                    {f ? (
                      <Badge tone={f.rating === "needs_work" ? "warning" : "success"}>
                        {f.rating === "needs_work" ? "needs work" : "excellent"}
                      </Badge>
                    ) : <span className="text-xs text-muted-foreground">fine</span>}
                  </button>
                );
              })}
            </div>
          ) : null}
        </div>
      ))}

      <form className="mb-2 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const v = newConcept.trim();
          if (v && !concepts.some((c) => c.concept === v)) {
            setConcepts((prev) => [...prev, { concept: v, flags: {} }]);
            setNewConcept("");
          }
        }}>
        <Input placeholder="Add a concept, e.g. Reading" value={newConcept}
          onChange={(e) => setNewConcept(e.target.value)} />
        <Button type="submit" variant="outline" disabled={!newConcept.trim()}><Plus className="h-4 w-4" /></Button>
      </form>

      <Button className="w-full" disabled={save.isPending || !name.trim()} onClick={() => save.mutate()}>
        {save.isPending ? "Saving…" : "Save section"}
      </Button>
    </div>
  );
}

function DeepLogSection({ card }: { card: PeriodCard }) {
  const qc = useQueryClient();
  const csId = card.class_subject_id;
  const [editing, setEditing] = useState<ObservationSection | null>(null);
  const [creating, setCreating] = useState(false);
  const { data } = useQuery({
    queryKey: ["observations", csId],
    queryFn: () => schoolApi.observations(csId!),
    enabled: !!csId,
  });
  const remove = useMutation({
    mutationFn: (section: string) => schoolApi.deleteObservationSection(csId!, section),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["observations", csId] }); toast.success("Section removed"); },
    onError: (e) => showApiError(e, "Could not remove"),
  });

  if (!csId) return null;
  const sections = data?.sections ?? [];

  return (
    <Section title="Lesson detail (optional)" icon={<Plus className="h-4 w-4" />}
      aside={!creating && !editing ? (
        <Button size="sm" variant="ghost" onClick={() => setCreating(true)}>
          <Plus className="h-4 w-4" /> Add section
        </Button>
      ) : null}>
      {sections.length === 0 && !creating ? (
        <p className="text-sm text-muted-foreground">
          Add a section like “Vocabulary” with concepts (“Reading”, “Writing”) and flag
          only the students who stood out — everything else is assumed fine.
        </p>
      ) : null}
      <div className="space-y-2">
        {sections.map((s) => (
          <div key={`${s.period_id ?? "day"}-${s.section}`} className="rounded-lg border border-border bg-background p-3">
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold">{s.section}</p>
              <div className="flex gap-1">
                <Button size="sm" variant="ghost" onClick={() => { setCreating(false); setEditing(s); }}>Edit</Button>
                <Button size="sm" variant="ghost" onClick={() => remove.mutate(s.section)}><X className="h-3.5 w-3.5" /></Button>
              </div>
            </div>
            {s.concepts.length > 0 ? (
              <ul className="mt-1 space-y-1 text-sm">
                {s.concepts.map((c, i) => (
                  <li key={i} className="flex flex-wrap items-center gap-1">
                    <span className="text-muted-foreground">{c.concept ?? "—"}</span>
                    {c.students.map((st) => (
                      <Badge key={st.student_id} tone={st.rating === "needs_work" ? "warning" : "success"}>
                        {st.full_name}
                      </Badge>
                    ))}
                    {c.students.length === 0 ? <span className="text-xs text-muted-foreground">· all fine</span> : null}
                  </li>
                ))}
              </ul>
            ) : null}
            {editing?.section === s.section ? (
              <SectionEditor card={card} existing={editing} onClose={() => setEditing(null)} />
            ) : null}
          </div>
        ))}
      </div>
      {creating ? <SectionEditor card={card} existing={null} onClose={() => setCreating(false)} /> : null}
    </Section>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────
// ── test capture (SC-2) — photograph today's evaluated test, confirm scores ──
function TestCaptureSection({ card }: { card: PeriodCard }) {
  const [captureId, setCaptureId] = useState<string | null>(null);
  const { data: classSubjects = [] } = useQuery({
    queryKey: ["class-subjects", card.class_id],
    queryFn: () => schoolApi.classSubjects(card.class_id),
    enabled: card.class_subject_id != null,
  });
  const subjectId = classSubjects.find((cs) => cs.id === card.class_subject_id)?.subject_id;
  const start = useStartCapture(setCaptureId);
  if (card.class_subject_id == null) return null;

  return (
    <Section title="Today's test" icon={<Camera className="h-4 w-4" />}
      aside={!captureId ? (
        <Button size="sm" variant="outline" disabled={!subjectId || start.isPending}
          onClick={() => start.mutate({
            cycle: { type: "daily_test", name: `${card.subject_name ?? "Test"} · ${card.date}`,
              date: card.date, class_id: card.class_id, subject_id: subjectId },
            class_id: card.class_id, subject_id: subjectId })}>
          {start.isPending ? "Starting…" : "Record a test"}
        </Button>
      ) : null}>
      {captureId ? (
        <CaptureReview captureId={captureId} onDone={() => setCaptureId(null)} />
      ) : (
        <p className="text-xs text-muted-foreground">
          Took a test this period? Photograph the evaluated papers — the scores read
          themselves; you just confirm.
        </p>
      )}
    </Section>
  );
}

function PeriodPageInner() {
  const params = useParams<{ classId: string; no: string }>();
  const classId = params.classId;
  const periodNo = Number(params.no);
  const qc = useQueryClient();
  const [notHeldOpen, setNotHeldOpen] = useState(false);
  const [reason, setReason] = useState("");
  // S-147: which approved event this period was lost to, if any. "" = free text,
  // which is S-146's per-class case (8-A went to the rehearsal, 8-B taught on).
  const [reasonEvent, setReasonEvent] = useState("");

  const { data: card, isLoading } = useQuery({
    queryKey: ["period-card", classId, periodNo],
    queryFn: () => schoolApi.periodCard(classId, periodNo),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["period-card", classId, periodNo] });
    qc.invalidateQueries({ queryKey: ["my-day"] });
  };

  const notHeld = useMutation({
    mutationFn: async () => {
      const periodId = card!.period_id
        ?? (await schoolApi.openPeriod({
          class_id: classId, period_no: periodNo, class_subject_id: card!.class_subject_id,
        })).id;
      return schoolApi.periodNotHeld(periodId, reason.trim(), reasonEvent || null);
    },
    onSuccess: () => { toast.success("Marked not held"); setNotHeldOpen(false); refresh(); },
    onError: (e) => showApiError(e, "Could not update"),
  });

  // "Save session" = close the period (drives the reminders + daily report).
  // It stays editable — "Edit session" reopens it.
  const closeSession = useMutation({
    mutationFn: async () => {
      const periodId = card!.period_id
        ?? (await schoolApi.openPeriod({
          class_id: classId, period_no: periodNo, class_subject_id: card!.class_subject_id,
        })).id;
      return schoolApi.closePeriod(periodId);
    },
    onSuccess: () => { toast.success("Session saved"); refresh(); },
    onError: (e) => showApiError(e, "Could not save session"),
  });
  const reopen = useMutation({
    mutationFn: () => schoolApi.reopenPeriod(card!.period_id!),
    onSuccess: () => { toast.success("Session reopened — make your changes"); refresh(); },
    onError: (e) => showApiError(e, "Could not reopen"),
  });

  if (isLoading || !card) {
    return <PageLoading label="Loading period…" />;
  }

  return (
    <div className="mx-auto max-w-2xl">
      {/* Whose birthday it is in the room she is walking into (founder,
          2026-08-05). One line, dismissible for the day, and this class only —
          the school's own calendar is the admin's notice, not hers. */}
      <div className="mb-3"><ClassDayNotice classId={classId} /></div>
      <div className="mb-4">
        <Link href="/my-day" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> My Day
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              P{card.period_no} · {card.combined_label ?? card.class_label}
              {card.subject_name ? ` · ${card.subject_name}` : ""}
            </h1>
            <p className="text-sm text-muted-foreground">
              {card.date}
              {card.combined_label ? (
                <span className="ml-1.5 inline-flex items-center gap-1 text-primary">
                  <Link2 className="h-3.5 w-3.5" /> taught together
                </span>
              ) : null}
            </p>
          </div>
          {card.status === "not_held" ? (
            <Badge tone="neutral">not held{card.not_held_reason ? ` · ${card.not_held_reason}` : ""}</Badge>
          ) : card.locked ? (
            <Badge tone="neutral">
              off today{card.lock_reason ? ` · ${card.lock_reason}` : ""}
            </Badge>
          ) : !notHeldOpen ? (
            <Button size="sm" variant="ghost" onClick={() => setNotHeldOpen(true)}>Period not held?</Button>
          ) : null}
        </div>
        {notHeldOpen && card.status !== "not_held" ? (
          <form className="mt-2 space-y-2"
            onSubmit={(e) => { e.preventDefault(); if (reason.trim()) notHeld.mutate(); }}>
            {/* S-147 — the reason points at the event when there is one, so the
                school can ask what a function cost it in periods. Free text
                stays available; it is not the key. */}
            {card.day_events.length ? (
              <div className="flex flex-wrap gap-1.5">
                {card.day_events.map((ev) => (
                  <button key={ev.id} type="button"
                    onClick={() => {
                      setReasonEvent(ev.id === reasonEvent ? "" : ev.id);
                      if (ev.id !== reasonEvent) setReason(ev.title);
                    }}
                    className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${
                      reasonEvent === ev.id
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-card hover:bg-muted"}`}>
                    {ev.title}
                  </button>
                ))}
              </div>
            ) : null}
            <div className="flex gap-2">
              <Input autoFocus placeholder="Why not? e.g. sports day" value={reason} onChange={(e) => setReason(e.target.value)} />
              <Button type="submit" size="sm" variant="outline" disabled={notHeld.isPending || !reason.trim()}>Confirm</Button>
              <Button type="button" size="sm" variant="ghost" onClick={() => setNotHeldOpen(false)}>Cancel</Button>
            </div>
          </form>
        ) : null}
      </div>

      {card.status === "not_held" ? (
        <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          This period was marked not held — nothing to capture.
        </p>
      ) : card.locked ? (
        /* S-145: the school itself closed this period. Nothing is expected —
           and what was already recorded against it is untouched (Q-65). */
        <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          {card.lock_reason ?? "The school"} — this period is off today, so
          nothing is being asked of you. Anything already recorded is kept.
        </p>
      ) : (
        <div className="space-y-3">
          {card.closed ? (
            <div className="flex items-center justify-between rounded-xl border border-[color:var(--success,#234a37)]/40 bg-[color:var(--success,#234a37)]/5 px-4 py-3">
              <p className="flex items-center gap-1.5 text-sm font-medium">
                <Check className="h-4 w-4 text-[color:var(--success,#234a37)]" /> Session saved
              </p>
              <Button size="sm" variant="outline" disabled={reopen.isPending}
                onClick={() => reopen.mutate()}>
                {reopen.isPending ? "Opening…" : "Edit session"}
              </Button>
            </div>
          ) : null}
          <AttendanceSection card={card} />
          <TopicSection card={card} onSaved={refresh} />
          <HomeworkSection card={card} onSaved={refresh} />
          <ChecksSection card={card} />
          <TestCaptureSection card={card} />
          <DeepLogSection card={card} />
          {!card.closed ? (
            <Button className="w-full" size="lg" disabled={closeSession.isPending}
              onClick={() => closeSession.mutate()}>
              {closeSession.isPending ? "Saving…" : "Save session ✓"}
            </Button>
          ) : null}
        </div>
      )}
    </div>
  );
}

export default function PeriodPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <PeriodPageInner />
    </AuthGuard>
  );
}
