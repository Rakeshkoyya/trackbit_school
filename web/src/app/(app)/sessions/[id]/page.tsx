"use client";

// Session capture — a guided flow, attendance first (P1v2 budget: 15 students in
// under a minute). Step 1 attendance (tap-cycle, all-present fast path), step 2
// homework check (homework board alongside for homework sessions, optional study
// notes for study sessions), step 3 wrap-up: summary + memories (batch
// photos/videos, never per student — P5). Re-opening a captured session lands on
// the wrap-up with edit shortcuts.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, ArrowRight, BookOpen, CalendarClock, Camera, Check, Film,
  Loader2, PlayCircle, Trash2, Users,
} from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { AttendanceStatus, Meeting, SessionDetail } from "@/lib/school-types";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const NEXT: Record<AttendanceStatus, AttendanceStatus> = { present: "late", late: "absent", absent: "present" };
const TONE: Record<AttendanceStatus, "success" | "warning" | "danger"> = {
  present: "success", late: "warning", absent: "danger",
};

type Step = "attendance" | "homework" | "done";
type Row = { status: AttendanceStatus; late_minutes: number | null; hw_done: boolean };

function StepDots({ step }: { step: Step }) {
  const order: Step[] = ["attendance", "homework", "done"];
  const labels = { attendance: "Attendance", homework: "Homework", done: "Wrap up" };
  return (
    <ol className="mb-4 flex items-center gap-2 text-xs">
      {order.map((s, i) => {
        const active = order.indexOf(step) === i;
        const passed = order.indexOf(step) > i;
        return (
          <li key={s} className="flex items-center gap-2">
            <span className={`grid h-5 w-5 place-items-center rounded-full text-[10px] font-bold ${passed ? "bg-[color:var(--success,#234a37)] text-white" : active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
              {passed ? <Check className="h-3 w-3" /> : i + 1}
            </span>
            <span className={active ? "font-semibold" : "text-muted-foreground"}>{labels[s]}</span>
            {i < order.length - 1 ? <span className="w-4 border-t border-border" /> : null}
          </li>
        );
      })}
    </ol>
  );
}

/** Homework board (HS): what each student was assigned today — the warden's
 *  reference while checking, read-only. */
function HomeworkBoard({ meetingId }: { meetingId: string }) {
  const { data: board, isLoading } = useQuery({
    queryKey: ["homework-board", meetingId],
    queryFn: () => schoolApi.homeworkBoard(meetingId),
  });
  if (isLoading) return <PageLoading label="Loading tonight’s homework…" />;
  if (!board) return null;
  const withItems = board.rows.filter((r) => r.items.length > 0);
  return (
    <div className="mb-3 rounded-lg border border-border bg-background p-3">
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
        <BookOpen className="h-3.5 w-3.5" /> Tonight’s homework
      </p>
      {withItems.length === 0 ? (
        <p className="text-sm text-muted-foreground">No open homework for this roster today.</p>
      ) : (
        <div className="space-y-2">
          {withItems.map((r) => (
            <div key={r.student_id}>
              <p className="text-sm font-medium">
                {r.full_name}
                {r.class_label ? <span className="ml-1 text-xs font-normal text-muted-foreground">· {r.class_label}</span> : null}
              </p>
              <ul className="mt-0.5 space-y-0.5">
                {r.items.map((i) => (
                  <li key={i.assignment_id} className="text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">{i.subject}:</span> {i.text}
                    {i.personal ? <Badge className="ml-1.5" tone="primary">personal</Badge> : null}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/** Memories (HS): batch photos/videos of the whole group — never per student (P5). */
function Memories({ meeting }: { meeting: Meeting }) {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["session-meeting", meeting.session_id] });
  const media = useMutation({
    mutationFn: (file: File) => schoolApi.uploadSessionMedia(meeting.id, file),
    onSuccess: () => { refresh(); toast.success("Added to memories"); },
    onError: (e) => showApiError(e, "Could not upload"),
  });
  const removeMedia = useMutation({
    mutationFn: (mediaId: string) => schoolApi.deleteSessionMedia(mediaId),
    onSuccess: () => { refresh(); toast.success("Removed"); },
    onError: (e) => showApiError(e, "Could not remove"),
  });
  return (
    <div className="mb-4">
      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
        <Camera className="h-3.5 w-3.5" /> Memories
      </p>
      {meeting.media.length > 0 ? (
        <div className="mb-2 grid grid-cols-3 gap-2 sm:grid-cols-4">
          {meeting.media.map((md) => (
            <div key={md.id} className="group relative overflow-hidden rounded-md border border-border">
              {md.kind === "video" ? (
                <video src={md.url} controls preload="metadata" className="aspect-square w-full object-cover" />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element -- R2 presigned URLs are dynamic hosts
                <img src={md.url} alt={md.caption ?? "Session memory"} className="aspect-square w-full object-cover" />
              )}
              <button onClick={() => removeMedia.mutate(md.id)}
                className="absolute right-1 top-1 hidden rounded-md bg-black/60 p-1 text-white group-hover:block"
                aria-label="Remove">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
              {md.caption ? (
                <p className="absolute inset-x-0 bottom-0 truncate bg-black/50 px-1.5 py-0.5 text-[11px] text-white">{md.caption}</p>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="mb-2 text-sm text-muted-foreground">
          {meeting.kind === "activity" ? "Capture the moment — one photo or video of the whole group." : "No photos yet."}
        </p>
      )}
      <div className="flex gap-2">
        <label className="inline-flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm hover:bg-muted/40">
          {media.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Camera className="h-4 w-4" />} Photo
          <input type="file" accept="image/*" capture="environment" className="hidden"
            onChange={(ev) => { const f = ev.target.files?.[0]; if (f) media.mutate(f); ev.target.value = ""; }} />
        </label>
        <label className="inline-flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm hover:bg-muted/40">
          <Film className="h-4 w-4" /> Video
          <input type="file" accept="video/*" className="hidden"
            onChange={(ev) => { const f = ev.target.files?.[0]; if (f) media.mutate(f); ev.target.value = ""; }} />
        </label>
      </div>
    </div>
  );
}

function CaptureFlow({ meeting, sessionName, onExit }: {
  meeting: Meeting; sessionName: string; onExit: () => void;
}) {
  const qc = useQueryClient();
  const alreadyCaptured = meeting.roster.some((r) => r.status != null);
  const [step, setStep] = useState<Step>(alreadyCaptured ? "done" : "attendance");
  const [rows, setRows] = useState<Record<string, Row>>(() =>
    Object.fromEntries(meeting.roster.map((r) => [r.student_id, {
      status: (r.status as AttendanceStatus) ?? "present",
      late_minutes: r.late_minutes,
      hw_done: r.homework_done ?? true,
    }])));
  // Study notes ride along only when touched (they're optional — P1v2).
  const [notes, setNotes] = useState<Record<string, string>>({});
  const noteOf = (studentId: string, fallback: string | null) => notes[studentId] ?? fallback ?? "";

  const patch = (id: string, p: Partial<Row>) =>
    setRows((prev) => ({ ...prev, [id]: { ...prev[id], ...p } }));

  const save = useMutation({
    mutationFn: async (next: Step) => {
      await schoolApi.recordAttendance(meeting.id, meeting.roster.map((r) => {
        const e = rows[r.student_id];
        return {
          student_id: r.student_id, status: e.status,
          late_minutes: e.status === "late" ? e.late_minutes ?? 0 : null,
          homework_done: e.status === "absent" ? null : e.hw_done,
        };
      }));
      const touched = meeting.roster
        .filter((r) => r.student_id in notes && (notes[r.student_id] ?? "") !== (r.log_note ?? ""))
        .map((r) => ({ student_id: r.student_id, note: notes[r.student_id] }));
      if (touched.length > 0) await schoolApi.setStudentLogs(meeting.id, touched);
      return next;
    },
    onSuccess: (next) => {
      qc.invalidateQueries({ queryKey: ["session-meeting", meeting.session_id] });
      toast.success("Saved");
      setStep(next);
    },
    onError: (e) => showApiError(e, "Could not save"),
  });

  const vals = Object.values(rows);
  const absent = vals.filter((r) => r.status === "absent").length;
  const late = vals.filter((r) => r.status === "late").length;
  const present = vals.length - absent;
  const hwMissing = meeting.roster.filter((r) => rows[r.student_id].status !== "absent" && !rows[r.student_id].hw_done).length;
  const saving = save.isPending;
  const isStudy = meeting.kind === "study";

  return (
    <div>
      <StepDots step={step} />

      {step === "attendance" ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h2 className="mb-1 flex items-center gap-1.5 text-sm font-semibold">
            <Users className="h-4 w-4" /> Who’s here?
          </h2>
          <p className="mb-3 text-xs text-muted-foreground">
            Everyone starts present — tap a name to cycle present → late → absent.
            {" "}{present}/{vals.length} present{late ? ` · ${late} late` : ""}{absent ? ` · ${absent} absent` : ""}
          </p>
          <div className="mb-3 grid gap-1 sm:grid-cols-2">
            {meeting.roster.map((r) => {
              const e = rows[r.student_id];
              return (
                <div key={r.student_id} className="flex items-center gap-1.5">
                  <button type="button" onClick={() => patch(r.student_id, { status: NEXT[e.status] })}
                    className="flex min-w-0 flex-1 items-center justify-between rounded-lg border border-border bg-background px-3 py-2 text-left text-sm active:scale-[0.99]">
                    <span className="truncate">{r.roll_no ? `${r.roll_no}. ` : ""}{r.full_name}</span>
                    <Badge tone={TONE[e.status]}>{e.status}</Badge>
                  </button>
                  {e.status === "late" ? (
                    <Input className="h-9 w-14 shrink-0" type="number" placeholder="min"
                      aria-label={`${r.full_name} minutes late`}
                      value={e.late_minutes ?? ""}
                      onChange={(ev) => patch(r.student_id, { late_minutes: ev.target.value ? Number(ev.target.value) : null })} />
                  ) : null}
                </div>
              );
            })}
          </div>
          <Button className="w-full" disabled={saving} onClick={() => save.mutate("homework")}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
            {absent || late ? "Save attendance & continue" : "All present ✓ — continue"}
          </Button>
        </section>
      ) : null}

      {step === "homework" ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h2 className="mb-1 flex items-center gap-1.5 text-sm font-semibold">
            <BookOpen className="h-4 w-4" /> Homework check
          </h2>
          <p className="mb-3 text-xs text-muted-foreground">
            Tap only the students who did <span className="font-semibold">not</span> do their homework.
            {isStudy ? " Add a note only where there’s something to say." : ""}
          </p>
          {meeting.kind === "homework" ? <HomeworkBoard meetingId={meeting.id} /> : null}
          <div className="mb-3 grid gap-1 sm:grid-cols-2">
            {meeting.roster.map((r) => {
              const e = rows[r.student_id];
              if (e.status === "absent") {
                return (
                  <div key={r.student_id} className="flex items-center justify-between rounded-lg border border-dashed border-border px-3 py-2 text-sm text-muted-foreground">
                    <span className="truncate line-through">{r.full_name}</span>
                    <span className="text-xs">absent</span>
                  </div>
                );
              }
              return (
                <div key={r.student_id}>
                  <button type="button" onClick={() => patch(r.student_id, { hw_done: !e.hw_done })}
                    className="flex w-full items-center justify-between rounded-lg border border-border bg-background px-3 py-2 text-left text-sm active:scale-[0.99]">
                    <span className="truncate">{r.roll_no ? `${r.roll_no}. ` : ""}{r.full_name}</span>
                    {e.hw_done ? <Badge tone="success">did it</Badge> : <Badge tone="warning">didn’t do it</Badge>}
                  </button>
                  {isStudy ? (
                    <Input className="mt-1 h-8 text-sm" placeholder="What did they work on? (optional)"
                      value={noteOf(r.student_id, r.log_note)}
                      onChange={(ev) => setNotes((p) => ({ ...p, [r.student_id]: ev.target.value }))} />
                  ) : null}
                </div>
              );
            })}
          </div>
          <div className="flex gap-2">
            <Button variant="ghost" onClick={() => setStep("attendance")} disabled={saving}>
              <ArrowLeft className="h-4 w-4" /> Back
            </Button>
            <Button className="flex-1" disabled={saving} onClick={() => save.mutate("done")}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <ArrowRight className="h-4 w-4" />}
              {hwMissing ? `Save — ${hwMissing} didn’t do it` : "Everyone did it ✓ — finish"}
            </Button>
          </div>
        </section>
      ) : null}

      {step === "done" ? (
        <section className="rounded-xl border border-border bg-card p-4">
          <h2 className="mb-3 flex items-center gap-1.5 text-sm font-semibold">
            <Check className="h-4 w-4 text-[color:var(--success,#234a37)]" /> {sessionName} · captured
          </h2>
          <div className="mb-4 grid grid-cols-3 gap-2 text-center">
            <div className="rounded-lg border border-border bg-background py-3">
              <p className="text-xl font-semibold">{present}/{vals.length}</p>
              <p className="text-xs text-muted-foreground">present</p>
            </div>
            <div className="rounded-lg border border-border bg-background py-3">
              <p className="text-xl font-semibold">{late}</p>
              <p className="text-xs text-muted-foreground">late</p>
            </div>
            <div className="rounded-lg border border-border bg-background py-3">
              <p className="text-xl font-semibold">{hwMissing}</p>
              <p className="text-xs text-muted-foreground">no homework</p>
            </div>
          </div>
          <Memories meeting={meeting} />
          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={() => setStep("attendance")}>Edit attendance</Button>
            <Button variant="outline" className="flex-1" onClick={() => setStep("homework")}>Edit homework</Button>
            <Button className="flex-1" onClick={onExit}>Done</Button>
          </div>
        </section>
      ) : null}
    </div>
  );
}

function RosterPreview({ session, onStart }: { session: SessionDetail; onStart: () => void }) {
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        <Users className="h-4 w-4" /> Roster
      </h2>
      {session.students.length === 0 ? (
        <p className="text-sm text-muted-foreground">No students in this session yet.</p>
      ) : (
        <ul className="grid gap-1 text-sm sm:grid-cols-2">
          {session.students.map((s) => (
            <li key={s.student_id} className="rounded-md border border-border bg-background px-3 py-1.5">
              {s.roll_no ? `${s.roll_no}. ` : ""}{s.full_name}
            </li>
          ))}
        </ul>
      )}
      <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
        <CalendarClock className="h-3.5 w-3.5" />
        “Take today’s session” opens attendance first, then the homework check — under a minute.
      </p>
      {session.students.length > 0 ? (
        <Button className="mt-3 w-full sm:hidden" onClick={onStart}>
          <PlayCircle className="h-4 w-4" /> Take today’s session
        </Button>
      ) : null}
    </section>
  );
}

function SessionInner({ id }: { id: string }) {
  const [capturing, setCapturing] = useState(false);
  const { data: session, isLoading } = useQuery({
    queryKey: ["session", id],
    queryFn: () => schoolApi.session(id),
  });
  // Get-or-create today's meeting — only once the teacher taps "Take session".
  const { data: meeting, isLoading: opening } = useQuery({
    queryKey: ["session-meeting", id],
    queryFn: () => schoolApi.openMeeting(id),
    enabled: capturing,
  });

  if (isLoading || !session) return <PageLoading label="Loading session…" />;

  return (
    <div className="mx-auto max-w-2xl pb-8">
      <Link href="/sessions" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Sessions
      </Link>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            {session.name}
            <Badge tone={session.kind === "activity" ? "success" : session.kind === "homework" ? "warning" : "neutral"}>{session.kind}</Badge>
          </h1>
          <p className="text-sm text-muted-foreground">
            {session.weekdays.map((d) => DOW[d]).join(" · ") || "no days set"}
            {session.time ? ` · ${session.time.slice(0, 5)}${session.end_time ? `–${session.end_time.slice(0, 5)}` : ""}` : ""}
            {" "}· {session.students.length} students
            {session.teacher_name ? ` · ${session.teacher_name}` : ""}
          </p>
        </div>
        {!capturing ? (
          <Button onClick={() => setCapturing(true)} disabled={session.students.length === 0}>
            <PlayCircle className="h-4 w-4" /> Take today’s session
          </Button>
        ) : null}
      </div>

      {!capturing ? (
        <RosterPreview session={session} onStart={() => setCapturing(true)} />
      ) : opening || !meeting ? (
        <PageLoading label="Opening today’s session…" />
      ) : (
        <CaptureFlow meeting={meeting} sessionName={session.name} onExit={() => setCapturing(false)} />
      )}
    </div>
  );
}

export default function SessionCapturePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <SessionInner id={id} />
    </AuthGuard>
  );
}
