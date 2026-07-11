"use client";

// The session page (HS-2) — attendance summary card (capture on its own page),
// a grouped/searchable roster table (click a student → their session page),
// and the whole-class memories strip. Per-student work (homework detail,
// sectioned study logs, personal photos) lives on the student page.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, Camera, Check, ChevronRight, Film, NotebookPen, Trash2, Users,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Dropdown, StudentTable } from "@/components/school/student-table";
import { Badge } from "@/components/ui/badge";
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

// ── 2 · roster table — grouped by class, searchable; click → student page ────
type ShowFilter = "all" | "not_done" | "done" | "absent";

function RosterSection({ sessionId, meeting, onSaved }: {
  sessionId: string; meeting: Meeting; onSaved: () => void;
}) {
  const router = useRouter();
  const [show, setShow] = useState<ShowFilter>("all");
  const isHomework = meeting.kind === "homework";

  // Homework checkbox: starts EMPTY each day; tick who finished (saves per tap).
  const tick = useMutation({
    mutationFn: (r: MeetingRow) => schoolApi.recordAttendance(meeting.id, [{
      student_id: r.student_id, status: r.status ?? "present",
      late_minutes: r.late_minutes, homework_done: !(r.homework_done === true),
    }]),
    onSuccess: () => onSaved(),
    onError: (e) => showApiError(e, "Could not save"),
  });

  const rows = meeting.roster
    .filter((r) =>
      show === "all" ? true
        : show === "absent" ? r.status === "absent"
          : show === "done" ? r.homework_done === true
            : r.homework_done !== true)
    .map((r) => ({ ...r, id: r.student_id, name: r.full_name }));

  const filterOptions: [string, string][] = isHomework
    ? [["all", "Everyone"], ["not_done", "Homework pending"], ["done", "Homework done"], ["absent", "Absent"]]
    : [["all", "Everyone"], ["absent", "Absent"]];

  return (
    <Section title="Students" icon={<Users className="h-4 w-4" />}
      aside={<span className="text-xs text-muted-foreground">{meeting.roster.length} on roster</span>}>
      <p className="mb-2 text-xs text-muted-foreground">
        {isHomework
          ? "Tick who finished tonight’s homework. Tap a student for their work, logs and photos."
          : "Tap a student to log their work and add their photos."}
      </p>
      <StudentTable
        rows={rows}
        filters={<Dropdown label="Show" value={show} options={filterOptions}
          onChange={(v) => setShow(v as ShowFilter)} />}
        onRowClick={(r) => router.push(`/sessions/${sessionId}/student/${r.id}`)}
        right={(r) => (
          <>
            {r.status === "absent" ? <Badge tone="danger">absent</Badge>
              : r.status === "late" ? <Badge tone="warning">late</Badge> : null}
            {r.log_count > 0 ? (
              <Badge tone="primary"><NotebookPen className="h-3 w-3" /> {r.log_count}</Badge>
            ) : null}
            {r.media_count > 0 ? (
              <Badge tone="neutral"><Camera className="h-3 w-3" /> {r.media_count}</Badge>
            ) : null}
            {isHomework ? (
              <button type="button" aria-label={`Homework done for ${r.name}`}
                disabled={r.status === "absent" || tick.isPending}
                onClick={(e) => { e.stopPropagation(); tick.mutate(r); }}
                className={`flex h-7 w-7 items-center justify-center rounded-md border transition-colors ${
                  r.homework_done === true
                    ? "border-[color:var(--success,#234a37)] bg-[#e7efe9] text-[#234a37]"
                    : "border-border text-transparent hover:border-muted-foreground"
                } ${r.status === "absent" ? "opacity-40" : ""}`}>
                <Check className="h-4 w-4" />
              </button>
            ) : (
              <ChevronRight className="h-4 w-4 text-muted-foreground" />
            )}
          </>
        )}
      />
    </Section>
  );
}

// ── 3 · class memories — whole-group photos/videos (per-student ones live on
// the student page) ───────────────────────────────────────────────────────────
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
  const pick = (accept: string, capture?: boolean) => (
    <input type="file" accept={accept} {...(capture ? { capture: "environment" as const } : {})} className="hidden"
      onChange={(ev) => { const f = ev.target.files?.[0]; if (f) upload.mutate(f); ev.target.value = ""; }} />
  );

  return (
    <Section title="Class memories" icon={<Camera className="h-4 w-4" />}
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
          Capture the whole group — a photo or a short video of the session.
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
              {session?.time ? ` · ${session.time.slice(0, 5)}${session.end_time ? `–${session.end_time.slice(0, 5)}` : ""}` : ""}
              {session && session.class_labels.length > 0 ? ` · ${session.class_labels.join(", ")}` : ""}
              {session?.weekdays.length ? ` · ${session.weekdays.map((d) => DOW[d]).join(" ")}` : ""}
            </p>
          </div>
          <Badge tone={kind === "activity" ? "success" : kind === "homework" ? "warning" : "primary"}>{kind}</Badge>
        </div>
      </div>

      <div className="space-y-3">
        <AttendanceCard sessionId={id} meeting={meeting} />
        <RosterSection sessionId={id} meeting={meeting} onSaved={refresh} />
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
