"use client";

// One student's evening (HS-2) — opened from the session roster table.
// Their homework in full (with the done tick), a sectioned study log like the
// class deep log ("Maths", "Revision" → note each), and their own photos/videos.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, BookOpen, Camera, Check, Film, NotebookPen, Plus, Trash2, X,
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
import type { SessionStudentCard, StudentLogEntry } from "@/lib/school-types";

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

// ── homework — the student's open items + the done tick ─────────────────────
function HomeworkSection({ card, onSaved }: { card: SessionStudentCard; onSaved: () => void }) {
  const tick = useMutation({
    mutationFn: () => schoolApi.recordAttendance(card.meeting_id, [{
      student_id: card.student_id, status: card.status ?? "present",
      late_minutes: card.late_minutes, homework_done: !(card.homework_done === true),
    }]),
    onSuccess: () => onSaved(),
    onError: (e) => showApiError(e, "Could not save"),
  });
  return (
    <Section title="Homework" icon={<BookOpen className="h-4 w-4" />}
      aside={
        <button type="button" onClick={() => tick.mutate()} disabled={tick.isPending}
          className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors ${
            card.homework_done === true
              ? "border-[color:var(--success,#234a37)] bg-[#e7efe9] text-[#234a37]"
              : "border-border text-muted-foreground hover:bg-muted"}`}>
          <Check className="h-3.5 w-3.5" /> {card.homework_done === true ? "Done" : "Mark done"}
        </button>
      }>
      {card.homework.length === 0 ? (
        <p className="text-sm text-muted-foreground">No open homework for {card.full_name.split(" ")[0]} today.</p>
      ) : (
        <ul className="space-y-2">
          {card.homework.map((i) => (
            <li key={i.assignment_id} className="rounded-lg border border-border bg-background px-3 py-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium">{i.subject}</span>
                <span className="flex shrink-0 items-center gap-1.5">
                  {i.personal ? <Badge tone="primary">personal</Badge> : null}
                  {i.due_date ? <span className="text-xs text-muted-foreground">due {i.due_date}</span> : null}
                </span>
              </div>
              <p className="mt-0.5 text-muted-foreground">{i.text}</p>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

// ── study log — named sections, full-replace on save (like the class deep log) ─
function StudyLogSection({ card, onSaved }: { card: SessionStudentCard; onSaved: () => void }) {
  const [entries, setEntries] = useState<StudentLogEntry[]>(card.logs);
  const [section, setSection] = useState("");
  const [note, setNote] = useState("");
  const dirty = JSON.stringify(entries) !== JSON.stringify(card.logs);

  const save = useMutation({
    mutationFn: () => schoolApi.setStudentLogs(card.meeting_id, card.student_id, entries),
    onSuccess: () => { toast.success("Log saved"); onSaved(); },
    onError: (e) => showApiError(e, "Could not save the log"),
  });

  const addEntry = () => {
    const s = section.trim();
    const n = note.trim();
    if (!n) return;
    if (entries.some((e) => e.section.toLowerCase() === s.toLowerCase())) {
      toast.error(`Section “${s || "General"}” already exists — edit it below.`);
      return;
    }
    setEntries((p) => [...p, { section: s, note: n }]);
    setSection(""); setNote("");
  };

  return (
    <Section title="Study log" icon={<NotebookPen className="h-4 w-4" />}
      aside={<span className="text-xs text-muted-foreground">optional</span>}>
      {entries.length === 0 ? (
        <p className="mb-3 text-sm text-muted-foreground">
          Note what {card.full_name.split(" ")[0]} worked on — a section per subject
          or activity (“Maths”, “Revision”), a line each.
        </p>
      ) : (
        <div className="mb-3 space-y-2">
          {entries.map((e, i) => (
            <div key={i} className="rounded-lg border border-border bg-background p-2.5">
              <div className="mb-1 flex items-center justify-between gap-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  {e.section || "General"}
                </p>
                <button type="button" aria-label={`Remove ${e.section || "General"}`}
                  onClick={() => setEntries((p) => p.filter((_, j) => j !== i))}
                  className="rounded p-1 text-muted-foreground hover:bg-muted">
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              <Input value={e.note}
                onChange={(ev) => setEntries((p) => p.map((x, j) => j === i ? { ...x, note: ev.target.value } : x))} />
            </div>
          ))}
        </div>
      )}

      <div className="rounded-lg border border-dashed border-border p-2.5">
        <div className="grid grid-cols-[7rem_1fr] gap-2">
          <Input placeholder="Section" value={section} aria-label="Section"
            onChange={(e) => setSection(e.target.value)} />
          <Input placeholder="What did they do?" value={note} aria-label="Note"
            onChange={(e) => setNote(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); addEntry(); } }} />
        </div>
        <Button type="button" variant="outline" size="sm" className="mt-2 w-full"
          onClick={addEntry} disabled={!note.trim()}>
          <Plus className="h-4 w-4" /> Add to log
        </Button>
      </div>

      {dirty ? (
        <Button className="mt-3 w-full" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? "Saving…" : "Save log"}
        </Button>
      ) : null}
    </Section>
  );
}

// ── the student's own memories ───────────────────────────────────────────────
function StudentMemories({ card, onSaved }: { card: SessionStudentCard; onSaved: () => void }) {
  const upload = useMutation({
    mutationFn: (file: File) =>
      schoolApi.uploadSessionMedia(card.meeting_id, file, { studentId: card.student_id }),
    onSuccess: () => { toast.success("Added"); onSaved(); },
    onError: (e) => showApiError(e, "Could not upload"),
  });
  const remove = useMutation({
    mutationFn: (mediaId: string) => schoolApi.deleteSessionMedia(mediaId),
    onSuccess: () => { toast.success("Removed"); onSaved(); },
    onError: (e) => showApiError(e, "Could not remove"),
  });
  const pick = (accept: string, capture?: boolean) => (
    <input type="file" accept={accept} {...(capture ? { capture: "environment" as const } : {})} className="hidden"
      onChange={(ev) => { const f = ev.target.files?.[0]; if (f) upload.mutate(f); ev.target.value = ""; }} />
  );

  return (
    <Section title={`${card.full_name.split(" ")[0]}’s memories`} icon={<Camera className="h-4 w-4" />}
      aside={upload.isPending ? <span className="text-xs text-muted-foreground">Uploading…</span> : null}>
      {card.media.length > 0 ? (
        <div className="mb-3 grid grid-cols-3 gap-2 sm:grid-cols-4">
          {card.media.map((md) => (
            <div key={md.id} className="group relative overflow-hidden rounded-md border border-border">
              {md.kind === "video" ? (
                <video src={md.url} controls preload="metadata" className="aspect-square w-full object-cover" />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element -- R2 presigned URLs are dynamic hosts
                <img src={md.url} alt={md.caption ?? "Memory"} className="aspect-square w-full object-cover" />
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
          A photo of their work or their moment tonight.
        </p>
      )}
      <div className="flex gap-2">
        <label className="flex flex-1 cursor-pointer items-center justify-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm font-medium hover:bg-muted/40">
          <Camera className="h-4 w-4" /> Photo
          {pick("image/*", true)}
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
function StudentSessionInner({ sessionId, studentId }: { sessionId: string; studentId: string }) {
  const qc = useQueryClient();
  // Meeting is get-or-create; the card hangs off it (deep links work too).
  const { data: meeting } = useQuery({
    queryKey: ["meeting", sessionId], queryFn: () => schoolApi.openMeeting(sessionId) });
  const { data: card, isLoading } = useQuery({
    queryKey: ["session-student", meeting?.id, studentId],
    queryFn: () => schoolApi.sessionStudentCard(meeting!.id, studentId),
    enabled: !!meeting,
  });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["session-student", meeting?.id, studentId] });
    qc.invalidateQueries({ queryKey: ["meeting", sessionId] });
  };

  if (isLoading || !card) {
    return <p className="py-12 text-center text-sm text-muted-foreground">Loading student…</p>;
  }

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4">
        <Link href={`/sessions/${sessionId}`}
          className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> {card.session_name}
        </Link>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold tracking-tight">{card.full_name}</h1>
            <p className="text-sm text-muted-foreground">
              {card.class_label ?? "No class"}{card.roll_no ? ` · Roll ${card.roll_no}` : ""} · {card.date}
            </p>
          </div>
          {card.status ? (
            <Badge tone={card.status === "absent" ? "danger" : card.status === "late" ? "warning" : "success"}>
              {card.status}{card.late_minutes ? ` ${card.late_minutes}m` : ""}
            </Badge>
          ) : <Badge tone="neutral">attendance not taken</Badge>}
        </div>
      </div>

      <div className="space-y-3">
        {card.kind !== "activity" ? <HomeworkSection card={card} onSaved={refresh} /> : null}
        <StudyLogSection key={JSON.stringify(card.logs)} card={card} onSaved={refresh} />
        <StudentMemories card={card} onSaved={refresh} />
      </div>
    </div>
  );
}

export default function SessionStudentPage({ params }: {
  params: Promise<{ id: string; studentId: string }>;
}) {
  const { id, studentId } = use(params);
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <StudentSessionInner sessionId={id} studentId={studentId} />
    </AuthGuard>
  );
}
