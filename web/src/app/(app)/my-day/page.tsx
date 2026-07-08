"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, Check, ClipboardCheck, ListChecks, Send, UserCheck, Users } from "lucide-react";
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
import type {
  AttendanceException,
  DailyCheck,
  HomeworkPending,
  MyDayClass,
  MyDayPeriod,
} from "@/lib/school-types";

type HwTarget = { csId: string; title: string; classId?: string; periodNo?: number };

function HomeworkSheet({ target, onClose }: { target: HwTarget | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [due, setDue] = useState("");
  const [studentId, setStudentId] = useState("");
  // Roster for the optional per-student addition (only when opened from a period).
  const { data: roster } = useQuery({
    queryKey: ["attendance-roster", target?.classId, target?.periodNo],
    queryFn: () => schoolApi.attendanceRoster(target!.classId!, target!.periodNo!),
    enabled: !!target?.classId && target?.periodNo != null,
  });
  const add = useMutation({
    mutationFn: () => schoolApi.addHomework({
      class_subject_id: target!.csId, text: text.trim(), due_date: due || null,
      student_id: studentId || null,
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["my-day"] });
      toast.success(`Homework set · ${res.notified_count} parents notified`);
      setText(""); setDue(""); setStudentId(""); onClose();
    },
    onError: (e) => showApiError(e, "Could not set homework"),
  });
  return (
    <Sheet open={!!target} onOpenChange={(v) => { if (!v) onClose(); }} title={target ? `Homework · ${target.title}` : ""}>
      <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) add.mutate(); }}>
        <Input autoFocus placeholder="e.g. Draw the water cycle" value={text} onChange={(e) => setText(e.target.value)} />
        {roster && roster.roster.length > 0 ? (
          <div>
            <label className="text-xs text-muted-foreground">For</label>
            <select className="h-9 w-full rounded-md border border-border bg-background px-2 text-sm"
              value={studentId} onChange={(e) => setStudentId(e.target.value)}>
              <option value="">Whole class</option>
              {roster.roster.map((r) => <option key={r.student_id} value={r.student_id}>{r.full_name}</option>)}
            </select>
          </div>
        ) : null}
        <div><label className="text-xs text-muted-foreground">Due (optional)</label><Input type="date" value={due} onChange={(e) => setDue(e.target.value)} /></div>
        <Button type="submit" className="w-full" disabled={add.isPending || !text.trim()}>
          <Send className="h-4 w-4" /> {add.isPending ? "Sending…" : "Set homework & notify parents"}
        </Button>
      </form>
    </Sheet>
  );
}

// Tap cycles a student present → absent → late → present (exception-only capture).
const NEXT: Record<string, AttendanceException | null> = {
  present: "absent", absent: "late", late: null,
};

function AttendanceSheet({ period, onClose }: { period: MyDayPeriod | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [marks, setMarks] = useState<Record<string, AttendanceException>>({});
  const [seedKey, setSeedKey] = useState("");
  const { data } = useQuery({
    queryKey: ["attendance-roster", period?.class_id, period?.period_no],
    queryFn: () => schoolApi.attendanceRoster(period!.class_id, period!.period_no),
    enabled: !!period,
  });

  // Seed the tapped-exceptions from the loaded roster during render (not in an
  // effect) — keyed on the open period so switching/reopening reseeds cleanly.
  const key = period && data ? `${period.class_id}:${period.period_no}` : "";
  if (key !== seedKey) {
    const initial: Record<string, AttendanceException> = {};
    if (data) for (const r of data.roster) if (r.status) initial[r.student_id] = r.status;
    setMarks(initial);
    setSeedKey(key);
  }

  const save = useMutation({
    mutationFn: () => schoolApi.markAttendance({
      class_id: period!.class_id, period_no: period!.period_no,
      class_subject_id: period!.class_subject_id,
      exceptions: Object.entries(marks).map(([student_id, status]) => ({ student_id, status })),
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["my-day"] });
      const alerted = res.alerted_count > 0 ? ` · ${res.alerted_count} parents alerted` : "";
      toast.success(`Attendance saved · ${res.present_count}/${res.roster_count} present${alerted}`);
      onClose();
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
  const late = Object.values(marks).filter((s) => s === "late").length;
  const total = data?.roster.length ?? 0;

  return (
    <Sheet open={!!period} onOpenChange={(v) => { if (!v) onClose(); }}
      title={period ? `Attendance · P${period.period_no} ${period.class_label}` : ""}>
      <p className="mb-3 text-xs text-muted-foreground">
        Everyone starts present — tap only those absent or late. {total - absent}/{total} present · {absent} absent · {late} late
      </p>
      <div className="mb-4 max-h-[50vh] space-y-1 overflow-y-auto">
        {data?.roster.map((r) => {
          const status = marks[r.student_id];
          const tone = status === "absent" ? "danger" : status === "late" ? "warning" : "success";
          const label = status ?? "present";
          return (
            <button key={r.student_id} type="button" onClick={() => cycle(r.student_id)}
              className="flex w-full items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-left text-sm active:scale-[0.99]">
              <span className="truncate">{r.roll_no ? `${r.roll_no}. ` : ""}{r.full_name}</span>
              <Badge tone={tone}>{label}</Badge>
            </button>
          );
        })}
      </div>
      <Button className="w-full" disabled={save.isPending} onClick={() => save.mutate()}>
        <UserCheck className="h-4 w-4" /> {save.isPending ? "Saving…" : "Save attendance"}
      </Button>
    </Sheet>
  );
}

// The teacher's recommended checks for this period — "Class did it ✓" one tap,
// then tap the students who didn't (exception capture, V2-P3 §5.5).
function ChecksSection({ period, onExceptions }: {
  period: MyDayPeriod; onExceptions: (check: DailyCheck) => void;
}) {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ["checks", period.class_subject_id],
    queryFn: () => schoolApi.checks(period.class_subject_id),
  });
  const confirm = useMutation({
    mutationFn: (checkId: string) => schoolApi.confirmCheck(checkId, []),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["checks", period.class_subject_id] }); toast.success("Marked done"); },
    onError: (e) => showApiError(e, "Could not confirm"),
  });
  if (!data || data.checks.length === 0) return null;
  return (
    <div className="mt-2 border-t border-border pt-2">
      <p className="mb-1.5 flex items-center gap-1 text-xs font-semibold text-muted-foreground">
        <ListChecks className="h-3.5 w-3.5" /> Today’s checks
      </p>
      <div className="space-y-1.5">
        {data.checks.map((c) => (
          <div key={c.id} className="flex items-start gap-2 text-sm">
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
              <button type="button" onClick={() => onExceptions(c)}
                className="shrink-0 rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted">
                <Check className="mr-0.5 inline h-3.5 w-3.5 text-[color:var(--success,#234a37)]" />edit
              </button>
            ) : (
              <div className="flex shrink-0 gap-1">
                <Button size="sm" onClick={() => confirm.mutate(c.id)} disabled={confirm.isPending}>Class did it</Button>
                <Button size="sm" variant="outline" onClick={() => onExceptions(c)}>Flag</Button>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function CheckExceptionsSheet({ target, onClose }: {
  target: { period: MyDayPeriod; check: DailyCheck } | null; onClose: () => void;
}) {
  const qc = useQueryClient();
  const [notDone, setNotDone] = useState<Record<string, true>>({});
  const [seedKey, setSeedKey] = useState("");
  const { data } = useQuery({
    queryKey: ["attendance-roster", target?.period.class_id, target?.period.period_no],
    queryFn: () => schoolApi.attendanceRoster(target!.period.class_id, target!.period.period_no),
    enabled: !!target,
  });
  const key = target ? target.check.id : "";
  if (key !== seedKey) {
    const initial: Record<string, true> = {};
    if (target) for (const r of target.check.results) if (r.status === "not_done") initial[r.student_id] = true;
    setNotDone(initial);
    setSeedKey(key);
  }
  const save = useMutation({
    mutationFn: () => schoolApi.confirmCheck(target!.check.id,
      Object.keys(notDone).map((student_id) => ({ student_id, status: "not_done" as const }))),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["checks", target!.period.class_subject_id] });
      toast.success("Saved");
      onClose();
    },
    onError: (e) => showApiError(e, "Could not save"),
  });
  const toggle = (id: string) => setNotDone((prev) => {
    const out = { ...prev };
    if (out[id]) delete out[id]; else out[id] = true;
    return out;
  });
  return (
    <Sheet open={!!target} onOpenChange={(v) => { if (!v) onClose(); }}
      title={target ? "Who didn’t do it?" : ""}>
      <p className="mb-3 text-xs text-muted-foreground">{target?.check.description}</p>
      <div className="mb-4 max-h-[50vh] space-y-1 overflow-y-auto">
        {data?.roster.map((r) => (
          <button key={r.student_id} type="button" onClick={() => toggle(r.student_id)}
            className="flex w-full items-center justify-between rounded-lg border border-border bg-card px-3 py-2 text-left text-sm active:scale-[0.99]">
            <span className="truncate">{r.roll_no ? `${r.roll_no}. ` : ""}{r.full_name}</span>
            {notDone[r.student_id] ? <Badge tone="warning">didn’t do it</Badge> : <Badge tone="success">did it</Badge>}
          </button>
        ))}
      </div>
      <Button className="w-full" disabled={save.isPending} onClick={() => save.mutate()}>
        {save.isPending ? "Saving…" : "Save checks"}
      </Button>
    </Sheet>
  );
}

function PeriodCard({ p, onAttendance, onHomework, onCheckExceptions }: {
  p: MyDayPeriod; onAttendance: () => void; onHomework: () => void;
  onCheckExceptions: (check: DailyCheck) => void;
}) {
  const qc = useQueryClient();
  const log = useMutation({
    mutationFn: (coverage: string) =>
      schoolApi.logLesson({ class_subject_id: p.class_subject_id, topic_id: p.planned_topic_id, coverage }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["my-day"] }); toast.success("Logged"); },
    onError: (e) => showApiError(e, "Could not log"),
  });
  const allPresent = useMutation({
    mutationFn: () => schoolApi.markAttendance({
      class_id: p.class_id, period_no: p.period_no, class_subject_id: p.class_subject_id, exceptions: [],
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["my-day"] });
      toast.success(`All present · ${res.present_count}/${res.roster_count}`);
    },
    onError: (e) => showApiError(e, "Could not mark attendance"),
  });

  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-3 flex items-center gap-3">
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-muted text-xs font-bold">P{p.period_no}</span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-semibold">{p.class_label} · {p.subject_name}</p>
          <p className="truncate text-xs text-muted-foreground">
            {p.planned_topic ? p.planned_topic : "No topic planned this week"}
          </p>
        </div>
      </div>

      {/* 1 · Attendance */}
      <div className="mb-2 flex items-center gap-2">
        <Users className="h-4 w-4 shrink-0 text-muted-foreground" />
        {p.attendance_marked ? (
          <>
            <Badge tone={p.absent_count ? "warning" : "success"}>
              {p.present_count}/{p.roster_count} present{p.absent_count ? ` · ${p.absent_count} absent` : ""}{p.late_count ? ` · ${p.late_count} late` : ""}
            </Badge>
            <Button size="sm" variant="ghost" onClick={onAttendance}>Edit</Button>
          </>
        ) : (
          <>
            <Button size="sm" onClick={() => allPresent.mutate()} disabled={allPresent.isPending || p.roster_count === 0}>
              All present
            </Button>
            <Button size="sm" variant="outline" onClick={onAttendance} disabled={p.roster_count === 0}>
              Mark absentees
            </Button>
            {p.roster_count === 0 ? <span className="text-xs text-muted-foreground">No students on roster</span> : null}
          </>
        )}
      </div>

      {/* 2 · Topic */}
      <div className="flex flex-wrap items-center gap-2">
        <Check className="h-4 w-4 shrink-0 text-muted-foreground" />
        {p.logged ? (
          <Badge tone="success">topic logged</Badge>
        ) : (
          <>
            <Button size="sm" onClick={() => log.mutate("full")} disabled={log.isPending}>Covered</Button>
            <Button size="sm" variant="outline" onClick={() => log.mutate("partial")} disabled={log.isPending}>Partially</Button>
          </>
        )}
        <Button size="sm" variant="ghost" onClick={onHomework}>
          <BookOpen className="h-4 w-4" /> Homework
        </Button>
      </div>

      {/* 3 · Checks (recommendations) */}
      <ChecksSection period={p} onExceptions={onCheckExceptions} />
    </div>
  );
}

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

function MyDayInner() {
  const [hwFor, setHwFor] = useState<HwTarget | null>(null);
  const [attFor, setAttFor] = useState<MyDayPeriod | null>(null);
  const [checkFor, setCheckFor] = useState<{ period: MyDayPeriod; check: DailyCheck } | null>(null);
  const { data } = useQuery({ queryKey: ["my-day"], queryFn: schoolApi.myDay });

  return (
    <div>
      <div className="mb-6">
        <PageHeader title="My Day" subtitle="Confirm each period by exception — attendance, topic, checks, homework in under a minute" />
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
          <div className="space-y-3">
            {data.periods.map((p) => (
              <PeriodCard key={`${p.period_no}-${p.class_subject_id}`} p={p}
                onAttendance={() => setAttFor(p)}
                onCheckExceptions={(check) => setCheckFor({ period: p, check })}
                onHomework={() => setHwFor({
                  csId: p.class_subject_id, classId: p.class_id, periodNo: p.period_no,
                  title: `${p.class_label} ${p.subject_name ?? ""}`.trim(),
                })} />
            ))}
          </div>
        </section>
      ) : null}

      <h2 className="mb-2 text-sm font-semibold">Today’s classes</h2>
      {!data || data.classes.length === 0 ? (
        <EmptyState icon={BookOpen} title="No classes assigned to you"
          body="Ask your admin to assign your subjects on the Setup → class page." />
      ) : (
        <div className="space-y-3">
          {data.classes.map((c) => (
            <ClassCard key={c.class_subject_id} c={c}
              onHomework={() => setHwFor({ csId: c.class_subject_id, title: `${c.class_label} ${c.subject_name}` })} />
          ))}
        </div>
      )}

      <HomeworkSheet target={hwFor} onClose={() => setHwFor(null)} />
      <AttendanceSheet period={attFor} onClose={() => setAttFor(null)} />
      <CheckExceptionsSheet target={checkFor} onClose={() => setCheckFor(null)} />
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
