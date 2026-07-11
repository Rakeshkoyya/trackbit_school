"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, Camera, Check, Film, Trash2 } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { AttendanceStatus, MeetingRow } from "@/lib/school-types";

type Edit = { status: AttendanceStatus; late_minutes: number | null; homework_done: boolean | null };
const NEXT: Record<AttendanceStatus, AttendanceStatus> = { present: "late", late: "absent", absent: "present" };
const STATUS_STYLE: Record<AttendanceStatus, string> = {
  present: "bg-[#e7efe9] text-[#234a37]",
  late: "bg-warning-soft text-warning",
  absent: "bg-muted text-muted-foreground line-through",
};

/** Homework board (HS): what each student was assigned today — read view. */
function HomeworkBoard({ meetingId }: { meetingId: string }) {
  const { data: board } = useQuery({
    queryKey: ["homework-board", meetingId],
    queryFn: () => schoolApi.homeworkBoard(meetingId),
  });
  if (!board) return null;
  const withItems = board.rows.filter((r) => r.items.length > 0);
  return (
    <section className="mt-6">
      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
        <BookOpen className="h-4 w-4" /> Tonight’s homework
      </h2>
      {withItems.length === 0 ? (
        <p className="text-sm text-muted-foreground">No open homework for this roster today.</p>
      ) : (
        <div className="space-y-2">
          {withItems.map((r) => (
            <div key={r.student_id} className="rounded-lg border border-border bg-card px-3 py-2">
              <p className="text-sm font-medium">
                {r.full_name}
                {r.class_label ? <span className="ml-1 text-xs font-normal text-muted-foreground">· {r.class_label}</span> : null}
              </p>
              <ul className="mt-1 space-y-0.5">
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
    </section>
  );
}

function CaptureInner({ id }: { id: string }) {
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  // open (get-or-create) today's meeting once
  const { data: meeting } = useQuery({ queryKey: ["meeting", id], queryFn: () => schoolApi.openMeeting(id) });

  const eff = (r: MeetingRow): Edit =>
    edits[r.student_id] ?? {
      status: (r.status as AttendanceStatus) ?? "present",
      late_minutes: r.late_minutes, homework_done: r.homework_done,
    };
  const setEdit = (r: MeetingRow, patch: Partial<Edit>) =>
    setEdits((p) => ({ ...p, [r.student_id]: { ...eff(r), ...patch } }));
  const noteOf = (r: MeetingRow) => notes[r.student_id] ?? r.log_note ?? "";

  const refresh = () => qc.invalidateQueries({ queryKey: ["meeting", id] });
  const save = useMutation({
    mutationFn: async () => {
      await schoolApi.recordAttendance(meeting!.id, meeting!.roster.map((r) => {
        const e = eff(r);
        return { student_id: r.student_id, status: e.status, late_minutes: e.status === "late" ? e.late_minutes ?? 0 : null, homework_done: e.homework_done };
      }));
      // Study notes ride along only when touched (they're optional — P1v2).
      const touched = meeting!.roster
        .filter((r) => r.student_id in notes && (notes[r.student_id] ?? "") !== (r.log_note ?? ""))
        .map((r) => ({ student_id: r.student_id, note: notes[r.student_id] }));
      if (touched.length > 0) await schoolApi.setStudentLogs(meeting!.id, touched);
    },
    onSuccess: () => { refresh(); setEdits({}); setNotes({}); toast.success("Saved"); },
    onError: (e) => showApiError(e, "Could not save"),
  });
  const media = useMutation({
    mutationFn: (file: File) => schoolApi.uploadSessionMedia(meeting!.id, file),
    onSuccess: () => { refresh(); toast.success("Added to memories"); },
    onError: (e) => showApiError(e, "Could not upload"),
  });
  const removeMedia = useMutation({
    mutationFn: (mediaId: string) => schoolApi.deleteSessionMedia(mediaId),
    onSuccess: () => { refresh(); toast.success("Removed"); },
    onError: (e) => showApiError(e, "Could not remove"),
  });

  if (!meeting) return null;
  const isStudy = meeting.kind === "study";

  return (
    <div className="pb-24">
      <Link href="/sessions" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Sessions
      </Link>
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Today’s session</h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Tap a name to cycle present → late → absent. Toggle homework.
        {isStudy ? " Add a note only where there’s something to say." : ""}
      </p>

      <div className="space-y-2">
        {meeting.roster.map((r) => {
          const e = eff(r);
          return (
            <div key={r.student_id} className="rounded-lg border border-border bg-card px-3 py-2.5">
              <div className="flex items-center gap-2">
                <button onClick={() => setEdit(r, { status: NEXT[e.status] })}
                  className={`min-w-0 flex-1 rounded-md px-3 py-2 text-left text-sm font-medium ${STATUS_STYLE[e.status]}`}>
                  {r.full_name} <span className="text-xs font-normal">· {e.status}</span>
                </button>
                {e.status === "late" ? (
                  <Input className="h-8 w-14" type="number" placeholder="min" value={e.late_minutes ?? ""}
                    onChange={(ev) => setEdit(r, { late_minutes: ev.target.value ? Number(ev.target.value) : null })} />
                ) : null}
                <button onClick={() => setEdit(r, { homework_done: !e.homework_done })}
                  className={`flex h-8 w-8 items-center justify-center rounded-md border ${e.homework_done ? "border-primary bg-accent text-accent-foreground" : "border-border text-muted-foreground"}`}
                  aria-label="Homework done" title="Homework done">
                  <Check className="h-4 w-4" />
                </button>
              </div>
              {isStudy && e.status !== "absent" ? (
                <Input className="mt-2 h-8 text-sm" placeholder="What did they work on? (optional)"
                  value={noteOf(r)}
                  onChange={(ev) => setNotes((p) => ({ ...p, [r.student_id]: ev.target.value }))} />
              ) : null}
            </div>
          );
        })}
      </div>

      {meeting.kind === "homework" ? <HomeworkBoard meetingId={meeting.id} /> : null}

      {/* Memories (HS): batch photos/videos of the meeting — never per student (P5). */}
      <section className="mt-6">
        <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold">
          <Camera className="h-4 w-4" /> Memories
        </h2>
        {meeting.media.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {meeting.kind === "activity" ? "Capture the moment — a photo or video of the whole group." : "No photos yet."}
          </p>
        ) : (
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 lg:grid-cols-6">
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
        )}
      </section>

      {/* Sticky footer: add media + Done */}
      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-card/95 px-4 py-3 backdrop-blur lg:pl-64">
        <div className="mx-auto flex max-w-2xl items-center gap-2 lg:max-w-4xl">
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm">
            <Camera className="h-4 w-4" /> Photo
            <input type="file" accept="image/*" capture="environment" className="hidden"
              onChange={(ev) => { const f = ev.target.files?.[0]; if (f) media.mutate(f); ev.target.value = ""; }} />
          </label>
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm">
            <Film className="h-4 w-4" /> Video
            <input type="file" accept="video/*" className="hidden"
              onChange={(ev) => { const f = ev.target.files?.[0]; if (f) media.mutate(f); ev.target.value = ""; }} />
          </label>
          <Button className="flex-1" onClick={() => save.mutate()} disabled={save.isPending || media.isPending}>
            {save.isPending ? "Saving…" : media.isPending ? "Uploading…" : "Done"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function SessionCapturePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <CaptureInner id={id} />
    </AuthGuard>
  );
}
