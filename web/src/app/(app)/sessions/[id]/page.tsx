"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Camera, Check, ImageIcon } from "lucide-react";
import Link from "next/link";
import { use, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
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

function CaptureInner({ id }: { id: string }) {
  const qc = useQueryClient();
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  // open (get-or-create) today's meeting once
  const { data: meeting } = useQuery({ queryKey: ["meeting", id], queryFn: () => schoolApi.openMeeting(id) });

  const eff = (r: MeetingRow): Edit =>
    edits[r.student_id] ?? {
      status: (r.status as AttendanceStatus) ?? "present",
      late_minutes: r.late_minutes, homework_done: r.homework_done,
    };
  const setEdit = (r: MeetingRow, patch: Partial<Edit>) =>
    setEdits((p) => ({ ...p, [r.student_id]: { ...eff(r), ...patch } }));

  const save = useMutation({
    mutationFn: () => schoolApi.recordAttendance(meeting!.id, meeting!.roster.map((r) => {
      const e = eff(r);
      return { student_id: r.student_id, status: e.status, late_minutes: e.status === "late" ? e.late_minutes ?? 0 : null, homework_done: e.homework_done };
    })),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["meeting", id] }); setEdits({}); toast.success("Attendance saved"); },
    onError: (e) => showApiError(e, "Could not save"),
  });
  const photo = useMutation({
    mutationFn: (file: File) => schoolApi.uploadEvidence(meeting!.id, file),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["meeting", id] }); toast.success("Photo attached"); },
    onError: (e) => showApiError(e, "Could not upload"),
  });

  if (!meeting) return null;

  return (
    <div className="pb-24">
      <Link href="/sessions" className="mb-4 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> Sessions
      </Link>
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Today’s session</h1>
      <p className="mb-4 text-sm text-muted-foreground">Tap a name to cycle present → late → absent. Toggle homework.</p>

      <div className="space-y-2">
        {meeting.roster.map((r) => {
          const e = eff(r);
          return (
            <div key={r.student_id} className="flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-2.5">
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
          );
        })}
      </div>

      {/* Sticky footer: one batch photo (P5) + Done */}
      <div className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-card/95 px-4 py-3 backdrop-blur lg:pl-64">
        <div className="mx-auto flex max-w-2xl items-center gap-2 lg:max-w-4xl">
          <label className="inline-flex cursor-pointer items-center gap-1.5 rounded-md border border-border px-3 py-2 text-sm">
            {meeting.evidence_url ? <ImageIcon className="h-4 w-4 text-primary" /> : <Camera className="h-4 w-4" />}
            {meeting.evidence_url ? "Photo added" : "Batch photo"}
            <input type="file" accept="image/*" capture="environment" className="hidden"
              onChange={(ev) => { const f = ev.target.files?.[0]; if (f) photo.mutate(f); }} />
          </label>
          <Button className="flex-1" onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Done"}
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
