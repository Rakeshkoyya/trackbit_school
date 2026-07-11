"use client";

// The session page — everything a teacher does for one hostel/after-school
// block, opened from Sessions, My Day ("This evening") or the hostel grid.
// Mirrors the period page: stacked section cards, each saving on its own.
// Attendance is a summary card that opens its own full-screen page.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, BookOpen, Camera, ChevronRight, Film, NotebookPen, Trash2, Users,
} from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { Meeting, MeetingRow } from "@/lib/school-types";

const DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

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

// ── 1 · attendance — summary card; capture lives on its own page ─────────────
function AttendanceCard({ sessionId, meeting }: { sessionId: string; meeting: Meeting }) {
  const marked = meeting.roster.some((r) => r.status != null);
  const present = meeting.roster.filter((r) => r.status === "present" || r.status === "late").length;
  const absent = meeting.roster.filter((r) => r.status === "absent");
  const late = meeting.roster.filter((r) => r.status === "late");
  const total = meeting.roster.length;

  return (
    <Section title="Attendance" icon={<Users className="h-4 w-4" />}
      aside={marked ? (
        <Link href={`/sessions/${sessionId}/attendance`}
          className="rounded-md px-2 py-1 text-xs text-muted-foreground hover:bg-muted">Edit</Link>
      ) : null}>
      {total === 0 ? (
        <p className="text-sm text-muted-foreground">No students on this session’s roster yet.</p>
      ) : marked ? (
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={absent.length ? "warning" : "success"}>{present}/{total} present</Badge>
            {absent.length ? <Badge tone="danger">{absent.length} absent</Badge> : null}
            {late.length ? <Badge tone="warning">{late.length} late</Badge> : null}
          </div>
          {absent.length || late.length ? (
            <ul className="mt-2 space-y-0.5 text-sm text-muted-foreground">
              {meeting.roster.filter((r) => r.status && r.status !== "present").map((r) => (
                <li key={r.student_id}>{r.full_name} — {r.status}{r.late_minutes ? ` (${r.late_minutes}m)` : ""}</li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : (
        <Link href={`/sessions/${sessionId}/attendance`}
          className="flex items-center justify-between rounded-lg border border-border bg-background px-3 py-2.5 text-sm font-medium transition-colors hover:bg-muted/40 active:scale-[0.99]">
          <span className="flex items-center gap-1.5"><Users className="h-4 w-4" /> Take attendance</span>
          <span className="flex items-center gap-1 text-xs font-normal text-muted-foreground">
            {total} students <ChevronRight className="h-4 w-4" />
          </span>
        </Link>
      )}
    </Section>
  );
}

// ── 2 · study notes (study kind) — optional per-student, one row at a time ───
function StudyNotesSection({ meeting, onSaved }: { meeting: Meeting; onSaved: () => void }) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const save = useMutation({
    mutationFn: (row: { student_id: string; note: string }) =>
      schoolApi.setStudentLogs(meeting.id, [row]),
    onSuccess: () => { setEditingId(null); onSaved(); },
    onError: (e) => showApiError(e, "Could not save the note"),
  });

  const open = (r: MeetingRow) => { setEditingId(r.student_id); setDraft(r.log_note ?? ""); };
  const withNotes = meeting.roster.filter((r) => r.log_note).length;

  return (
    <Section title="Study notes" icon={<NotebookPen className="h-4 w-4" />}
      aside={withNotes ? <span className="text-xs text-muted-foreground">{withNotes} noted</span> : null}>
      <p className="mb-2 text-xs text-muted-foreground">
        Optional — tap a student to note what they worked on tonight.
      </p>
      <div className="space-y-1">
        {meeting.roster.map((r) => (
          <div key={r.student_id}>
            {editingId === r.student_id ? (
              <form className="rounded-lg border border-primary/40 bg-background p-2"
                onSubmit={(e) => { e.preventDefault(); save.mutate({ student_id: r.student_id, note: draft }); }}>
                <p className="mb-1.5 text-sm font-medium">{r.full_name}</p>
                <Input autoFocus placeholder="e.g. Finished Maths Ex 4.2, revised Science ch. 3"
                  value={draft} onChange={(e) => setDraft(e.target.value)} />
                <div className="mt-2 flex gap-2">
                  <Button type="submit" size="sm" className="flex-1" disabled={save.isPending}>
                    {save.isPending ? "Saving…" : draft.trim() ? "Save note" : r.log_note ? "Clear note" : "Save"}
                  </Button>
                  <Button type="button" size="sm" variant="ghost" onClick={() => setEditingId(null)}>Cancel</Button>
                </div>
              </form>
            ) : (
              <button type="button" onClick={() => open(r)}
                className={`flex w-full items-center justify-between gap-2 rounded-lg border border-border px-3 py-2 text-left text-sm active:scale-[0.99] ${r.status === "absent" ? "opacity-50" : "bg-background hover:bg-muted/40"}`}>
                <span className="min-w-0 flex-1">
                  <span className="font-medium">{r.full_name}</span>
                  {r.log_note ? (
                    <span className="mt-0.5 block truncate text-xs text-muted-foreground">{r.log_note}</span>
                  ) : null}
                </span>
                {r.status === "absent"
                  ? <Badge tone="neutral">absent</Badge>
                  : r.log_note
                    ? <NotebookPen className="h-3.5 w-3.5 shrink-0 text-[color:var(--success,#234a37)]" />
                    : <span className="shrink-0 text-xs text-muted-foreground">add note</span>}
              </button>
            )}
          </div>
        ))}
      </div>
    </Section>
  );
}

// ── 3 · homework board (homework kind) — read view + done-by-exception ───────
function HomeworkBoardSection({ meeting, onSaved }: { meeting: Meeting; onSaved: () => void }) {
  const { data: board } = useQuery({
    queryKey: ["homework-board", meeting.id],
    queryFn: () => schoolApi.homeworkBoard(meeting.id),
  });
  // Local toggles; a Save bar appears only once something changed.
  const [dirty, setDirty] = useState<Record<string, boolean>>({});
  const statusOf = new Map(meeting.roster.map((r) => [r.student_id, r] as const));
  const save = useMutation({
    mutationFn: () => schoolApi.recordAttendance(meeting.id, Object.entries(dirty).map(([student_id, done]) => ({
      student_id, status: statusOf.get(student_id)?.status ?? "present",
      late_minutes: statusOf.get(student_id)?.late_minutes ?? null, homework_done: done,
    }))),
    onSuccess: () => { setDirty({}); toast.success("Homework marked"); onSaved(); },
    onError: (e) => showApiError(e, "Could not save"),
  });

  if (!board) return null;
  const doneOf = (id: string) => dirty[id] ?? statusOf.get(id)?.homework_done ?? true;

  return (
    <Section title="Tonight’s homework" icon={<BookOpen className="h-4 w-4" />}>
      <p className="mb-2 text-xs text-muted-foreground">
        Everyone starts done — tap a student who didn’t finish.
      </p>
      <div className="space-y-1.5">
        {board.rows.map((r) => {
          const absent = statusOf.get(r.student_id)?.status === "absent";
          const done = doneOf(r.student_id);
          return (
            <button key={r.student_id} type="button" disabled={absent}
              onClick={() => setDirty((p) => ({ ...p, [r.student_id]: !done }))}
              className={`w-full rounded-lg border px-3 py-2 text-left active:scale-[0.99] ${absent ? "border-border opacity-50" : done ? "border-border bg-background hover:bg-muted/40" : "border-warning/50 bg-warning-soft/40"}`}>
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium">
                  {r.full_name}
                  {r.class_label ? <span className="ml-1 text-xs font-normal text-muted-foreground">· {r.class_label}</span> : null}
                </span>
                {absent ? <Badge tone="neutral">absent</Badge>
                  : done ? <Badge tone="success">done</Badge> : <Badge tone="warning">not done</Badge>}
              </div>
              {r.items.length > 0 ? (
                <ul className="mt-1 space-y-0.5">
                  {r.items.map((i) => (
                    <li key={i.assignment_id} className="truncate text-xs text-muted-foreground">
                      <span className="font-medium text-foreground/80">{i.subject}:</span> {i.text}
                      {i.personal ? " · personal" : ""}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-0.5 text-xs text-muted-foreground/70">No open homework</p>
              )}
            </button>
          );
        })}
      </div>
      {Object.keys(dirty).length > 0 ? (
        <Button className="mt-3 w-full" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save homework status"}
        </Button>
      ) : null}
    </Section>
  );
}

// ── 4 · memories — batch photos/videos of the meeting, never per student ─────
function MemoriesSection({ meeting, onSaved }: { meeting: Meeting; onSaved: () => void }) {
  const upload = useMutation({
    mutationFn: (file: File) => schoolApi.uploadSessionMedia(meeting.id, file),
    onSuccess: () => { toast.success("Added to memories"); onSaved(); },
    onError: (e) => showApiError(e, "Could not upload"),
  });
  const remove = useMutation({
    mutationFn: (mediaId: string) => schoolApi.deleteSessionMedia(mediaId),
    onSuccess: () => { toast.success("Removed"); onSaved(); },
    onError: (e) => showApiError(e, "Could not remove"),
  });
  const pick = (accept: string, capture?: string) => (
    <input type="file" accept={accept} {...(capture ? { capture: "environment" as const } : {})} className="hidden"
      onChange={(ev) => { const f = ev.target.files?.[0]; if (f) upload.mutate(f); ev.target.value = ""; }} />
  );

  return (
    <Section title="Memories" icon={<Camera className="h-4 w-4" />}
      aside={upload.isPending ? <span className="text-xs text-muted-foreground">Uploading…</span> : null}>
      {meeting.media.length > 0 ? (
        <div className="mb-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
          {meeting.media.map((md) => (
            <div key={md.id} className="group relative overflow-hidden rounded-md border border-border">
              {md.kind === "video" ? (
                <video src={md.url} controls preload="metadata" className="aspect-square w-full object-cover" />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element -- R2 presigned URLs are dynamic hosts
                <img src={md.url} alt={md.caption ?? "Session memory"} className="aspect-square w-full object-cover" />
              )}
              <button onClick={() => remove.mutate(md.id)} aria-label="Remove"
                className="absolute right-1 top-1 rounded-md bg-black/60 p-1 text-white opacity-0 transition-opacity focus:opacity-100 group-hover:opacity-100">
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      ) : (
        <p className="mb-3 text-sm text-muted-foreground">
          Capture the moment — a group photo or a short video of the session.
        </p>
      )}
      <div className="flex gap-2">
        <label className="flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-muted/40">
          <Camera className="h-4 w-4" /> Photo
          {pick("image/*", "environment")}
        </label>
        <label className="flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-muted/40">
          <Film className="h-4 w-4" /> Video
          {pick("video/*")}
        </label>
      </div>
    </Section>
  );
}

// ── page ─────────────────────────────────────────────────────────────────────
function SessionPageInner({ id }: { id: string }) {
  const qc = useQueryClient();
  const { data: session } = useQuery({ queryKey: ["session", id], queryFn: () => schoolApi.session(id) });
  // Opening today's meeting is get-or-create, so the page is always operable.
  const { data: meeting, isLoading } = useQuery({ queryKey: ["meeting", id], queryFn: () => schoolApi.openMeeting(id) });
  const refresh = () => qc.invalidateQueries({ queryKey: ["meeting", id] });

  if (isLoading || !meeting) {
    return <p className="py-12 text-center text-sm text-muted-foreground">Loading session…</p>;
  }
  const kind = meeting.kind;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4">
        <Link href="/sessions" className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> Sessions
        </Link>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold tracking-tight">{session?.name ?? "Session"}</h1>
            <p className="text-sm text-muted-foreground">
              {meeting.date}
              {session?.time ? ` · ${session.time}${session.end_time ? `–${session.end_time}` : ""}` : ""}
              {session && session.class_labels.length > 0 ? ` · ${session.class_labels.join(", ")}` : ""}
              {session?.weekdays.length ? ` · ${session.weekdays.map((d) => DOW[d]).join(" ")}` : ""}
            </p>
          </div>
          <Badge tone={kind === "activity" ? "success" : kind === "homework" ? "warning" : "primary"}>{kind}</Badge>
        </div>
      </div>

      <div className="space-y-3">
        <AttendanceCard sessionId={id} meeting={meeting} />
        {kind === "study" ? <StudyNotesSection meeting={meeting} onSaved={refresh} /> : null}
        {kind === "homework" ? <HomeworkBoardSection meeting={meeting} onSaved={refresh} /> : null}
        <MemoriesSection meeting={meeting} onSaved={refresh} />
      </div>
    </div>
  );
}

export default function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <SessionPageInner id={id} />
    </AuthGuard>
  );
}
