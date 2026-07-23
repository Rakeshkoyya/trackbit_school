"use client";

// Full-screen attendance for a session meeting — opened from the session page.
// Same capture language as school attendance: everyone starts present, tap a
// student to cycle present → absent → late; late shows a minutes field.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, UserCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { AttendanceStatus, MeetingRow } from "@/lib/school-types";

const NEXT: Record<AttendanceStatus, AttendanceStatus> = {
  present: "absent", absent: "late", late: "present",
};
const TONE: Record<AttendanceStatus, "success" | "danger" | "warning"> = {
  present: "success", absent: "danger", late: "warning",
};

type Edit = { status: AttendanceStatus; late_minutes: number | null };

function AttendanceInner({ id }: { id: string }) {
  const qc = useQueryClient();
  const router = useRouter();
  const [edits, setEdits] = useState<Record<string, Edit>>({});
  const { data: session } = useQuery({ queryKey: ["session", id], queryFn: () => schoolApi.session(id) });
  const { data: meeting, isLoading } = useQuery({ queryKey: ["meeting", id], queryFn: () => schoolApi.openMeeting(id) });

  const eff = (r: MeetingRow): Edit =>
    edits[r.student_id] ?? { status: (r.status as AttendanceStatus) ?? "present", late_minutes: r.late_minutes };
  const setEdit = (r: MeetingRow, patch: Partial<Edit>) =>
    setEdits((p) => ({ ...p, [r.student_id]: { ...eff(r), ...patch } }));

  const save = useMutation({
    // Full roster every time: "saved" = every student has a row (all-present included).
    mutationFn: (rows: { student_id: string; status: AttendanceStatus; late_minutes: number | null }[]) =>
      schoolApi.recordAttendance(meeting!.id, rows.map((r) => ({
        ...r, homework_done: meeting!.roster.find((x) => x.student_id === r.student_id)?.homework_done ?? null,
      }))),
    onSuccess: (m) => {
      qc.setQueryData(["meeting", id], m);
      const present = m.roster.filter((r) => r.status === "present" || r.status === "late").length;
      toast.success(`Attendance saved · ${present}/${m.roster.length} present`);
      router.push(`/sessions/${id}`);
    },
    onError: (e) => showApiError(e, "Could not save attendance"),
  });

  if (isLoading || !meeting) {
    return <p className="py-12 text-center text-sm text-muted-foreground">Loading roster…</p>;
  }

  const rows = meeting.roster;
  const marked = rows.some((r) => r.status != null);
  const untouched = Object.keys(edits).length === 0;
  const counts = rows.reduce((acc, r) => { acc[eff(r).status] += 1; return acc; },
    { present: 0, absent: 0, late: 0 } as Record<AttendanceStatus, number>);

  const allPresent = () => save.mutate(rows.map((r) => ({ student_id: r.student_id, status: "present" as const, late_minutes: null })));
  const saveAll = () => save.mutate(rows.map((r) => {
    const e = eff(r);
    return { student_id: r.student_id, status: e.status, late_minutes: e.status === "late" ? e.late_minutes ?? 0 : null };
  }));

  return (
    <div className="mx-auto max-w-2xl pb-40 lg:pb-24">
      <div className="mb-4">
        <Link href={`/sessions/${id}`} className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> {session?.name ?? "Session"}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">Attendance</h1>
        <p className="text-sm text-muted-foreground">
          Everyone starts present — tap a student to cycle present → absent → late.
        </p>
      </div>

      {!marked && untouched ? (
        <Button className="mb-3 w-full" disabled={save.isPending} onClick={allPresent}>
          <UserCheck className="h-4 w-4" /> All present ✓
        </Button>
      ) : null}

      <div className="grid gap-1 sm:grid-cols-2">
        {rows.map((r) => {
          const e = eff(r);
          return (
            <div key={r.student_id} className="flex items-center gap-2">
              <button type="button" onClick={() => setEdit(r, { status: NEXT[e.status] })}
                className="flex min-w-0 flex-1 items-center justify-between rounded-lg border border-border bg-card px-3 py-2.5 text-left text-sm active:scale-[0.99]">
                <span className="truncate">{r.roll_no ? `${r.roll_no}. ` : ""}{r.full_name}</span>
                <Badge tone={TONE[e.status]}>{e.status}</Badge>
              </button>
              {e.status === "late" ? (
                <Input className="h-9 w-16 shrink-0" type="number" min={0} placeholder="min"
                  aria-label={`Minutes late for ${r.full_name}`} value={e.late_minutes ?? ""}
                  onChange={(ev) => setEdit(r, { late_minutes: ev.target.value ? Number(ev.target.value) : null })} />
              ) : null}
            </div>
          );
        })}
      </div>

      {/* Sticky save — one thumb, one tap. Sits above the mobile bottom-tab bar
          (h-16) and clears the desktop sidebar; pads for the home indicator. */}
      <div className="fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-30 border-t border-border bg-card/95 px-4 pt-3 pb-3 backdrop-blur lg:bottom-0 lg:z-40 lg:pl-64 lg:pb-3">
        <div className="mx-auto flex max-w-2xl items-center gap-3">
          <p className="shrink-0 text-xs text-muted-foreground">
            {counts.present + counts.late}/{rows.length} present
            {counts.absent ? ` · ${counts.absent} absent` : ""}{counts.late ? ` · ${counts.late} late` : ""}
          </p>
          <Button className="flex-1" disabled={save.isPending || rows.length === 0} onClick={saveAll}>
            <UserCheck className="h-4 w-4" /> {save.isPending ? "Saving…" : "Save attendance"}
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function SessionAttendancePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <AttendanceInner id={id} />
    </AuthGuard>
  );
}
