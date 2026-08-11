"use client";

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useParams, useRouter } from "next/navigation";
import { Camera, ChevronLeft, Home, StickyNote, Users } from "lucide-react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  RollCall, marksFrom, rollCounts,
  type RollMarks, type RollRow,
} from "@/components/school/roll-call";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { HomeworkSheet, Meeting } from "@/lib/school-types";

/**
 * Capturing a period that is not a subject (TT-2).
 *
 * The screen is assembled from `meeting.capture`, which the server derives from
 * `core/day_shape.CAPTURE` — so a games period offers attendance and photos and
 * nothing else, an extra course adds a class log, and the homework class adds
 * the class → subject → books walk. The teacher never sees a section her block
 * does not keep, and the API would refuse the write anyway.
 */

// ── homework verdicts ────────────────────────────────────────────────────────
// `done` is the ABSENCE of a row (see `core/homework_verdict.py`), so cycling
// back to "did it" removes the exception rather than storing one. Same
// vocabulary as the desk's check sheet, deliberately.
const CYCLE: (string | null)[] = [null, "not_done", "partial", "late", "carried", "waived"];
const VERDICT_LABEL: Record<string, string> = {
  done: "did it", not_done: "didn't", partial: "partly",
  late: "late", carried: "was away", waived: "let go",
};
const VERDICT_TONE: Record<string, "success" | "warning" | "neutral"> = {
  done: "success", late: "success", partial: "warning",
  not_done: "warning", carried: "neutral", waived: "neutral",
};

function BlockHomeworkSheet({ meetingId, assignmentId, onSaved, onMedia }: {
  meetingId: string; assignmentId: string; onSaved: () => void; onMedia: () => void;
}) {
  const [marks, setMarks] = useState<Record<string, string | null>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [seeded, setSeeded] = useState<string | null>(null);
  const [noteFor, setNoteFor] = useState<string | null>(null);
  const [uploading, setUploading] = useState<string | null>(null);

  /** A photo of this child's book, tagged to the child (`session_media`). */
  const attach = async (studentId: string, file: File) => {
    setUploading(studentId);
    try {
      await schoolApi.uploadBlockMedia(meetingId, file, { studentId });
      onMedia();
      toast.success("Photo added");
    } catch (e) {
      showApiError(e, "Could not add the photo");
    } finally {
      setUploading(null);
    }
  };

  const { data: sheet } = useQuery<HomeworkSheet>({
    queryKey: ["block-hw-sheet", meetingId, assignmentId],
    queryFn: () => schoolApi.blockHomeworkSheet(meetingId, assignmentId),
  });

  // Seed from the server's copy once per assignment — adjusted during render,
  // which is React's own answer for "reset state when the input changes".
  if (sheet && seeded !== assignmentId) {
    const next: Record<string, string | null> = {};
    const noteNext: Record<string, string> = {};
    for (const r of sheet.roster) {
      next[r.student_id] = r.status === "done" ? null : r.status;
      if (r.note) noteNext[r.student_id] = r.note;
    }
    setSeeded(assignmentId);
    setMarks(next);
    setNotes(noteNext);
  }

  const save = useMutation({
    mutationFn: () => schoolApi.checkBlockHomework(
      meetingId, assignmentId,
      Object.entries(marks)
        .filter(([, v]) => v !== null)
        .map(([student_id, status]) => ({
          student_id, status: status as string, note: notes[student_id]?.trim() || null,
        })),
    ),
    onSuccess: () => { toast.success("Homework recorded"); onSaved(); },
    onError: (e) => showApiError(e, "Could not save"),
  });

  if (!sheet) return <div className="h-32 animate-pulse rounded-lg bg-muted" />;

  const cycle = (id: string) => setMarks((prev) => {
    const at = CYCLE.indexOf(prev[id] ?? null);
    return { ...prev, [id]: CYCLE[(at + 1) % CYCLE.length] };
  });

  return (
    <div className="space-y-3">
      {!sheet.checked ? (
        <p className="rounded-md bg-muted/40 px-3 py-2 text-xs text-muted-foreground">
          Nobody has been through this yet — every child reads <b>not checked</b>{" "}
          until you save. Tap a name to record what you actually saw.
        </p>
      ) : null}

      <div className="flex gap-2">
        <Button size="sm" className="flex-1" disabled={save.isPending}
                onClick={() => { setMarks({}); save.mutate(); }}>
          Everyone did it
        </Button>
        <Button size="sm" variant="outline" className="flex-1" disabled={save.isPending}
                onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save what I marked"}
        </Button>
      </div>

      <ul className="divide-y divide-border rounded-lg border border-border">
        {sheet.roster.map((r) => {
          const v = marks[r.student_id] ?? (sheet.checked ? "done" : null);
          return (
            <li key={r.student_id} className="px-3 py-2">
              <div className="flex items-center gap-2">
                <button type="button" onClick={() => cycle(r.student_id)}
                        className="min-w-0 flex-1 text-left">
                  <span className="block truncate text-sm">
                    {r.roll_no ? `${r.roll_no}. ` : ""}{r.full_name}
                  </span>
                  {r.absent_when_set ? (
                    <span className="text-xs text-muted-foreground">was away when it was set</span>
                  ) : r.miss_streak >= 2 ? (
                    <span className="text-xs text-warning">{r.miss_streak} in a row</span>
                  ) : null}
                </button>
                <Badge tone={v ? VERDICT_TONE[v] ?? "neutral" : "neutral"}>
                  {v ? VERDICT_LABEL[v] ?? v : "not checked"}
                </Badge>
                <button type="button" aria-label="Add a note for this child"
                        onClick={() => setNoteFor(noteFor === r.student_id ? null : r.student_id)}
                        className="rounded p-1 text-muted-foreground hover:bg-muted">
                  <StickyNote className="h-4 w-4" />
                </button>
                <label className="cursor-pointer rounded p-1 text-muted-foreground hover:bg-muted"
                       aria-label="Photo of this child's work">
                  <Camera className={`h-4 w-4 ${uploading === r.student_id ? "opacity-40" : ""}`} />
                  <input
                    type="file" accept="image/*" className="hidden"
                    disabled={uploading === r.student_id}
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) attach(r.student_id, f);
                      e.target.value = "";
                    }}
                  />
                </label>
              </div>
              {noteFor === r.student_id ? (
                <div className="mt-2">
                  <Input
                    value={notes[r.student_id] ?? ""} placeholder="Note for this child (optional)"
                    className="h-8 text-xs"
                    onChange={(e) => setNotes((p) => ({ ...p, [r.student_id]: e.target.value }))}
                  />
                  <p className="mt-1 text-xs text-muted-foreground">
                    The note saves with the verdict; the camera attaches a photo
                    of this child&apos;s work straight away.
                  </p>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** class tabs → subject tabs → the homework given → the books (TT-2 §3). */
function HomeworkSection({ meeting }: { meeting: Meeting }) {
  const qc = useQueryClient();
  const [classId, setClassId] = useState<string>(meeting.class_options[0]?.class_id ?? "");
  const [csId, setCsId] = useState<string>("");

  const { data } = useQuery({
    queryKey: ["block-hw", meeting.id, classId, csId],
    queryFn: () => schoolApi.blockHomework(meeting.id, {
      classId: classId || undefined, classSubjectId: csId || undefined }),
    enabled: !!classId,
  });

  if (meeting.class_options.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
        No classes in this block tonight.
      </p>
    );
  }

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold">Homework</h2>

      <div className="flex flex-wrap gap-1.5">
        {meeting.class_options.map((c) => (
          <button key={c.class_id} type="button"
                  onClick={() => { setClassId(c.class_id); setCsId(""); }}
                  className={`rounded-full px-3 py-1 text-xs ${
                    classId === c.class_id
                      ? "bg-primary text-primary-foreground"
                      : "border border-border text-muted-foreground hover:bg-muted"}`}>
            {c.label}
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {(data?.subjects ?? []).map((s) => (
          <button key={s.class_subject_id} type="button"
                  onClick={() => setCsId(s.class_subject_id === csId ? "" : s.class_subject_id)}
                  className={`rounded-full px-3 py-1 text-xs ${
                    csId === s.class_subject_id
                      ? "bg-foreground text-background"
                      : "border border-border text-muted-foreground hover:bg-muted"}`}>
            {s.subject_name}
            {s.open_count ? ` · ${s.open_count}` : ""}
          </button>
        ))}
      </div>

      {(data?.assignments ?? []).length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
          {csId ? "Nothing set for this subject tonight." : "Pick a subject to see what was set."}
        </p>
      ) : (
        <div className="space-y-4">
          {(data?.assignments ?? []).map((a) => (
            <div key={a.assignment_id} className="rounded-xl border border-border bg-card p-3">
              <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-semibold">{a.subject_name}</p>
                  <p className="text-sm">{a.text}</p>
                  <p className="text-xs text-muted-foreground">
                    set {a.assigned_on}{a.due_date ? ` · due ${a.due_date}` : ""}
                  </p>
                </div>
                <Badge tone={a.checked ? "success" : "neutral"}>
                  {a.checked ? "checked" : "not checked"}
                </Badge>
              </div>
              <BlockHomeworkSheet
                meetingId={meeting.id} assignmentId={a.assignment_id}
                onSaved={() => {
                  qc.invalidateQueries({ queryKey: ["block-hw", meeting.id] });
                  qc.invalidateQueries({
                    queryKey: ["block-hw-sheet", meeting.id, a.assignment_id] });
                }}
                onMedia={() => qc.invalidateQueries({
                  queryKey: ["block-meeting", meeting.session_id] })}
              />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function RollSection({ meeting }: { meeting: Meeting }) {
  const qc = useQueryClient();
  const rows: RollRow[] = meeting.roster.map((r) => ({
    student_id: r.student_id, full_name: r.full_name, roll_no: r.roll_no,
  }));
  const [marks, setMarks] = useState<RollMarks>(() =>
    marksFrom(rows, (r) => {
      const hit = meeting.roster.find((x) => x.student_id === r.student_id);
      return { status: hit?.status ?? "present", late_minutes: hit?.late_minutes ?? null };
    }));
  const counts = rollCounts(marks);

  const save = useMutation({
    mutationFn: () => schoolApi.blockAttendance(
      meeting.id,
      rows.map((r) => ({
        student_id: r.student_id,
        status: marks[r.student_id]?.status ?? "present",
        late_minutes: marks[r.student_id]?.late_minutes ?? null,
      })),
    ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["block-meeting", meeting.session_id] });
      toast.success("Attendance saved");
    },
    onError: (e) => showApiError(e, "Could not save attendance"),
  });

  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
        Nobody is on this block&apos;s roster yet.
      </p>
    );
  }

  return (
    <section className="space-y-3">
      <div className="flex items-baseline justify-between gap-2">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold">
          <Users className="h-4 w-4" /> Attendance
        </h2>
        <p className="text-xs text-muted-foreground">
          {counts.present} present · {counts.absent} away
          {counts.late ? ` · ${counts.late} late` : ""}
        </p>
      </div>
      <RollCall rows={rows} marks={marks} onChange={setMarks} showLateMinutes />
      <Button className="w-full" disabled={save.isPending} onClick={() => save.mutate()}>
        {save.isPending ? "Saving…" : "Save attendance"}
      </Button>
    </section>
  );
}

function NoteSection({ meeting }: { meeting: Meeting }) {
  const qc = useQueryClient();
  const [text, setText] = useState(meeting.note ?? "");
  const save = useMutation({
    mutationFn: () => schoolApi.setBlockNote(meeting.id, text.trim() || null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["block-meeting", meeting.session_id] });
      toast.success("Class log saved");
    },
    onError: (e) => showApiError(e, "Could not save the log"),
  });
  return (
    <section className="space-y-2">
      <h2 className="text-sm font-semibold">Class log</h2>
      <textarea
        value={text} rows={3} placeholder="What did you cover today?"
        onChange={(e) => setText(e.target.value)}
        className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm"
      />
      <Button size="sm" variant="outline" disabled={save.isPending} onClick={() => save.mutate()}>
        {save.isPending ? "Saving…" : "Save log"}
      </Button>
    </section>
  );
}

function MemoriesSection({ meeting }: { meeting: Meeting }) {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(false);

  const upload = async (file: File) => {
    setBusy(true);
    try {
      await schoolApi.uploadBlockMedia(meeting.id, file);
      qc.invalidateQueries({ queryKey: ["block-meeting", meeting.session_id] });
      toast.success("Added");
    } catch (e) {
      showApiError(e, "Could not upload");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="space-y-2">
      <h2 className="flex items-center gap-1.5 text-sm font-semibold">
        <Camera className="h-4 w-4" /> Memories
      </h2>
      <label className="block">
        <span className="sr-only">Add a photo or video</span>
        <input
          type="file" accept="image/*,video/*" disabled={busy}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }}
          className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-primary file:px-3 file:py-2 file:text-primary-foreground"
        />
      </label>
      {busy ? <p className="text-xs text-muted-foreground">Uploading…</p> : null}
      {meeting.media.length ? (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {meeting.media.map((md) => (
            <a key={md.id} href={md.url} target="_blank" rel="noreferrer"
               className="shrink-0 overflow-hidden rounded-lg border border-border">
              {md.kind === "photo" ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={md.url} alt={md.caption ?? "Memory"} className="h-24 w-24 object-cover" />
              ) : (
                <span className="grid h-24 w-24 place-items-center bg-muted text-xs">video</span>
              )}
            </a>
          ))}
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">No photos yet.</p>
      )}
    </section>
  );
}

function BlockInner() {
  const params = useParams<{ blockId: string }>();
  const router = useRouter();
  const blockId = params.blockId;

  const { data: meeting, isError } = useQuery({
    queryKey: ["block-meeting", blockId],
    queryFn: () => schoolApi.openBlock(blockId),
    enabled: !!blockId,
    retry: false,
  });

  if (isError) {
    return (
      <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
        This block isn&apos;t yours to take. Ask your admin to add you to its staff.
      </p>
    );
  }
  if (!meeting) return <div className="h-40 animate-pulse rounded-xl bg-muted" />;

  const cap = meeting.capture;
  return (
    <div className="space-y-6 pb-16">
      <div>
        <button type="button" onClick={() => router.push("/my-day")}
                className="mb-2 flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
          <ChevronLeft className="h-3.5 w-3.5" /> My Day
        </button>
        <h1 className="text-lg font-semibold">{meeting.session_name}</h1>
        <p className="flex flex-wrap items-center gap-1.5 text-xs text-muted-foreground">
          <span>{meeting.kind_label}</span>
          <span>·</span>
          <span>{meeting.date}</span>
          {meeting.category_name ? (
            <Badge tone="neutral">
              <Home className="h-3 w-3" /> {meeting.category_name.toLowerCase()}s only
            </Badge>
          ) : null}
        </p>
      </div>

      {cap.homework_check ? <HomeworkSection meeting={meeting} /> : null}
      {cap.roll ? <RollSection meeting={meeting} /> : null}
      {cap.class_log ? <NoteSection meeting={meeting} /> : null}
      {cap.memories ? <MemoriesSection meeting={meeting} /> : null}
    </div>
  );
}

export default function BlockPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <BlockInner />
    </AuthGuard>
  );
}
