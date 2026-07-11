"use client";

// The period page — everything a teacher does for one class-period, opened from
// a My Day row. Attendance + topic are the core loop; homework, checks and the
// deep log (sections → concepts → tapped students) are optional extras (P1v2).

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, BookOpen, Check, ChevronDown, ChevronRight, ListChecks, Plus,
  Send, UserCheck, Users, X,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type {
  AttendanceException, DailyCheck, ObservationSection, PeriodCard,
} from "@/lib/school-types";

// Tap cycles a student present → absent → late → present (exception-only capture).
const NEXT: Record<string, AttendanceException | null> = {
  present: "absent", absent: "late", late: null,
};

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

// ── 1 · attendance (inline tap-cycle roster) ─────────────────────────────────
function AttendanceSection({ card, onSaved }: { card: PeriodCard; onSaved: () => void }) {
  const [editing, setEditing] = useState(!card.attendance_marked);
  const [marks, setMarks] = useState<Record<string, AttendanceException>>(() => {
    const initial: Record<string, AttendanceException> = {};
    for (const r of card.roster) if (r.status) initial[r.student_id] = r.status;
    return initial;
  });
  const save = useMutation({
    mutationFn: (exceptions: { student_id: string; status: AttendanceException }[]) =>
      schoolApi.markAttendance({
        class_id: card.class_id, period_no: card.period_no,
        class_subject_id: card.class_subject_id, exceptions,
      }),
    onSuccess: (res) => {
      const alerted = res.alerted_count > 0 ? ` · ${res.alerted_count} parents alerted` : "";
      toast.success(`Attendance saved · ${res.present_count}/${res.roster_count} present${alerted}`);
      setEditing(false);
      onSaved();
    },
    onError: (e) => showApiError(e, "Could not save attendance"),
  });

  const cycle = (id: string) => setMarks((prev) => {
    const cur = prev[id] ?? "present";
    const next = NEXT[cur];
    const out = { ...prev };
    if (next === null) delete out[id];
    else out[id] = next;
    return out;
  });

  const absent = Object.values(marks).filter((s) => s === "absent").length;
  const total = card.roster.length;

  if (card.roster.length === 0) {
    return (
      <Section title="Attendance" icon={<Users className="h-4 w-4" />}>
        <p className="text-sm text-muted-foreground">No students on this class’s roster yet.</p>
      </Section>
    );
  }

  if (!editing && card.attendance_marked) {
    return (
      <Section title="Attendance" icon={<Users className="h-4 w-4" />}
        aside={<Button size="sm" variant="ghost" onClick={() => setEditing(true)}>Edit</Button>}>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={card.absent_count ? "warning" : "success"}>
            {card.present_count}/{card.roster_count} present
          </Badge>
          {card.absent_count ? <Badge tone="danger">{card.absent_count} absent</Badge> : null}
          {card.late_count ? <Badge tone="warning">{card.late_count} late</Badge> : null}
        </div>
        {card.absent_count || card.late_count ? (
          <ul className="mt-2 space-y-0.5 text-sm text-muted-foreground">
            {card.roster.filter((r) => r.status).map((r) => (
              <li key={r.student_id}>{r.full_name} — {r.status}{r.late_minutes ? ` (${r.late_minutes}m)` : ""}</li>
            ))}
          </ul>
        ) : null}
      </Section>
    );
  }

  return (
    <Section title="Attendance" icon={<Users className="h-4 w-4" />}>
      <p className="mb-2 text-xs text-muted-foreground">
        Everyone starts present — tap only those absent or late. {total - absent}/{total} present
      </p>
      {!card.attendance_marked && Object.keys(marks).length === 0 ? (
        <Button className="mb-3 w-full" disabled={save.isPending} onClick={() => save.mutate([])}>
          <UserCheck className="h-4 w-4" /> All present ✓
        </Button>
      ) : null}
      <div className="mb-3 grid gap-1 sm:grid-cols-2">
        {card.roster.map((r) => {
          const status = marks[r.student_id];
          const tone = status === "absent" ? "danger" : status === "late" ? "warning" : "success";
          return (
            <button key={r.student_id} type="button" onClick={() => cycle(r.student_id)}
              className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-3 py-2 text-left text-sm active:scale-[0.99]">
              <span className="truncate">{r.roll_no ? `${r.roll_no}. ` : ""}{r.full_name}</span>
              <Badge tone={tone}>{status ?? "present"}</Badge>
            </button>
          );
        })}
      </div>
      <Button className="w-full" disabled={save.isPending}
        onClick={() => save.mutate(Object.entries(marks).map(([student_id, status]) => ({ student_id, status })))}>
        <UserCheck className="h-4 w-4" /> {save.isPending ? "Saving…" : "Save attendance"}
      </Button>
    </Section>
  );
}

// ── 2 · topics — several can fit in one period; one can span many days ───────
function TopicSection({ card, onSaved }: { card: PeriodCard; onSaved: () => void }) {
  const { plan } = card;
  const [adding, setAdding] = useState(plan.logged.length === 0);
  const [topicId, setTopicId] = useState(plan.planned_topic_id ?? "");
  const [note, setNote] = useState("");
  const log = useMutation({
    mutationFn: (coverage: string) => schoolApi.logLesson({
      class_subject_id: card.class_subject_id!, topic_id: topicId || null, coverage,
      note: note.trim() || null, period_no: card.period_no,
    }),
    onSuccess: () => { toast.success("Topic logged"); setNote(""); setAdding(false); onSaved(); },
    onError: (e) => showApiError(e, "Could not log"),
  });
  const remove = useMutation({
    mutationFn: (id: string) => schoolApi.deleteLog(id),
    onSuccess: () => { toast.success("Removed"); onSaved(); },
    onError: (e) => showApiError(e, "Could not remove"),
  });

  // Group the syllabus list by chapter so the picker reads like the plan.
  const byUnit = new Map<string, typeof plan.progress>();
  for (const row of plan.progress) {
    if (!byUnit.has(row.unit_title)) byUnit.set(row.unit_title, []);
    byUnit.get(row.unit_title)!.push(row);
  }

  if (card.class_subject_id == null) {
    return (
      <Section title="Topics taught" icon={<Check className="h-4 w-4" />}>
        <p className="text-sm text-muted-foreground">No subject is timetabled for this period.</p>
      </Section>
    );
  }

  return (
    <Section title="Topics taught" icon={<Check className="h-4 w-4" />}
      aside={!adding ? (
        <Button size="sm" variant="ghost" onClick={() => setAdding(true)}>
          <Plus className="h-4 w-4" /> {plan.logged.length > 0 ? "Add another topic" : "Add topic"}
        </Button>
      ) : null}>

      {plan.logged.length > 0 ? (
        <ul className="mb-1 space-y-1">
          {plan.logged.map((l) => (
            <li key={l.id} className="flex items-center gap-2 rounded-lg border border-border bg-background px-3 py-2 text-sm">
              <Check className="h-4 w-4 shrink-0 text-[color:var(--success,#234a37)]" />
              <span className="min-w-0 flex-1">
                <span className="font-medium">{l.topic_title ?? "No specific topic"}</span>
                {l.note ? <span className="text-muted-foreground"> — {l.note}</span> : null}
              </span>
              <Badge tone={l.coverage === "full" ? "success" : "warning"}>
                {l.coverage === "full" ? "covered" : "continues"}
              </Badge>
              <button type="button" aria-label="Remove log" onClick={() => remove.mutate(l.id)}
                className="shrink-0 rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
                <X className="h-3.5 w-3.5" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      {adding ? (
        <div className={plan.logged.length > 0 ? "mt-2 border-t border-border pt-3" : ""}>
          {plan.planned_topic_title ? (
            <p className="mb-2 text-xs text-muted-foreground">
              Planned this week: <span className="font-medium text-foreground">{plan.planned_topic_title}</span>
              {plan.planned_unit_title ? ` (${plan.planned_unit_title})` : ""}
            </p>
          ) : null}
          {plan.progress.length > 0 ? (
            <select
              aria-label="Topic taught"
              className="mb-2 h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
              value={topicId} onChange={(e) => setTopicId(e.target.value)}>
              <option value="">No specific topic</option>
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
            <p className="mb-2 text-sm text-muted-foreground">No syllabus loaded for this subject yet.</p>
          )}
          <Input className="mb-3" placeholder="Note (optional)" value={note} onChange={(e) => setNote(e.target.value)} />
          <div className="flex gap-2">
            <Button className="flex-1" onClick={() => log.mutate("full")} disabled={log.isPending}>Covered ✓</Button>
            <Button className="flex-1" variant="outline" onClick={() => log.mutate("partial")} disabled={log.isPending}>
              Partially — continues
            </Button>
            {plan.logged.length > 0 ? (
              <Button variant="ghost" onClick={() => setAdding(false)}>Cancel</Button>
            ) : null}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">
            “Partially” keeps the topic in tomorrow’s list — one topic can run across many days,
            and you can log several topics in the same period.
          </p>
        </div>
      ) : null}
    </Section>
  );
}

// ── 3 · homework — class-wide or per-student ─────────────────────────────────
function HomeworkSection({ card, onSaved }: { card: PeriodCard; onSaved: () => void }) {
  const [text, setText] = useState("");
  const [due, setDue] = useState("");
  const [studentId, setStudentId] = useState("");
  const [adding, setAdding] = useState(false);
  const nameOf = new Map(card.roster.map((r) => [r.student_id, r.full_name]));
  const add = useMutation({
    mutationFn: () => schoolApi.addHomework({
      class_subject_id: card.class_subject_id!, text: text.trim(),
      due_date: due || null, student_id: studentId || null,
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
function PeriodPageInner() {
  const params = useParams<{ classId: string; no: string }>();
  const classId = params.classId;
  const periodNo = Number(params.no);
  const qc = useQueryClient();
  const [notHeldOpen, setNotHeldOpen] = useState(false);
  const [reason, setReason] = useState("");

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
      return schoolApi.periodNotHeld(periodId, reason.trim());
    },
    onSuccess: () => { toast.success("Marked not held"); setNotHeldOpen(false); refresh(); },
    onError: (e) => showApiError(e, "Could not update"),
  });

  if (isLoading || !card) {
    return <PageLoading label="Loading period…" />;
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4">
        <Link href="/my-day" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> My Day
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              P{card.period_no} · {card.class_label}{card.subject_name ? ` · ${card.subject_name}` : ""}
            </h1>
            <p className="text-sm text-muted-foreground">{card.date}</p>
          </div>
          {card.status === "not_held" ? (
            <Badge tone="neutral">not held{card.not_held_reason ? ` · ${card.not_held_reason}` : ""}</Badge>
          ) : !notHeldOpen ? (
            <Button size="sm" variant="ghost" onClick={() => setNotHeldOpen(true)}>Period not held?</Button>
          ) : null}
        </div>
        {notHeldOpen && card.status !== "not_held" ? (
          <form className="mt-2 flex gap-2"
            onSubmit={(e) => { e.preventDefault(); if (reason.trim()) notHeld.mutate(); }}>
            <Input autoFocus placeholder="Why not? e.g. sports day" value={reason} onChange={(e) => setReason(e.target.value)} />
            <Button type="submit" size="sm" variant="outline" disabled={notHeld.isPending || !reason.trim()}>Confirm</Button>
            <Button type="button" size="sm" variant="ghost" onClick={() => setNotHeldOpen(false)}>Cancel</Button>
          </form>
        ) : null}
      </div>

      {card.status === "not_held" ? (
        <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          This period was marked not held — nothing to capture.
        </p>
      ) : (
        <div className="space-y-3">
          <AttendanceSection key={`att-${card.attendance_marked}`} card={card} onSaved={refresh} />
          <TopicSection key={`topic-${card.plan.logged.length}`} card={card} onSaved={refresh} />
          <HomeworkSection card={card} onSaved={refresh} />
          <ChecksSection card={card} />
          <DeepLogSection card={card} />
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
