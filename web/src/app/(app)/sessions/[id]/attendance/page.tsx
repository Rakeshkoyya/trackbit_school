"use client";

// Full-screen attendance for a session meeting — opened from the session page.
//
// V1-3 (S-12): renders the SAME RollCall component as the school period sheet,
// so one act has one habit — everyone present, tap the exceptions, with "Call
// the roll" for teachers who prefer name-by-name. Session storage stays a full
// roster row per student (that is this module's shape); only the UI unified.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, UserCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  RollCall,
  marksFrom,
  rollCounts,
  type RollMarks,
} from "@/components/school/roll-call";
import { Button } from "@/components/ui/button";
import { PageError } from "@/components/ui/page-error";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { AttendanceStatus } from "@/lib/school-types";

function AttendanceInner({ id }: { id: string }) {
  const qc = useQueryClient();
  const router = useRouter();
  const [marks, setMarks] = useState<RollMarks | null>(null);
  const [rollMode, setRollMode] = useState(false);
  const { data: session } = useQuery({ queryKey: ["session", id], queryFn: () => schoolApi.session(id) });
  const { data: meeting, isLoading, error } = useQuery({
    queryKey: ["meeting", id], queryFn: () => schoolApi.openMeeting(id), retry: false });

  if (meeting && marks === null) {
    setMarks(marksFrom(meeting.roster, (r) => {
      const row = meeting.roster.find((x) => x.student_id === r.student_id);
      return { status: row?.status, late_minutes: row?.late_minutes };
    }));
  }

  const save = useMutation({
    // Full roster every time: "saved" = every student has a row (all-present included).
    mutationFn: (m: RollMarks) =>
      schoolApi.recordAttendance(meeting!.id, meeting!.roster.map((r) => ({
        student_id: r.student_id,
        status: (m[r.student_id]?.status ?? "present") as AttendanceStatus,
        late_minutes: m[r.student_id]?.status === "late"
          ? m[r.student_id]?.late_minutes ?? 0 : null,
        homework_done: r.homework_done ?? null,
      }))),
    onSuccess: (m) => {
      qc.setQueryData(["meeting", id], m);
      const present = m.roster.filter((r) => r.status === "present" || r.status === "late").length;
      toast.success(`Attendance saved · ${present}/${m.roster.length} present`);
      router.push(`/sessions/${id}`);
    },
    onError: (e) => showApiError(e, "Could not save attendance"),
  });

  // The error branch comes FIRST. A failed query leaves `isLoading` false and
  // the data undefined, so folding the two into one spinner condition renders
  // "Loading roster…" forever on a plain 403 — which is exactly how a refused
  // register reached the founder as "stuck loading" instead of as a sentence.
  if (error) {
    return (
      <PageError error={error} fallback="Could not load this roster."
        action={
          <Button variant="outline" onClick={() => router.push(`/sessions/${id}`)}>
            Back to the session
          </Button>
        } />
    );
  }
  if (isLoading || !meeting || marks === null) {
    return <p className="py-12 text-center text-sm text-muted-foreground">Loading roster…</p>;
  }

  const counts = rollCounts(marks);

  return (
    <div className="mx-auto max-w-2xl pb-40 lg:pb-24">
      <div className="mb-4">
        <Link href={`/sessions/${id}`} className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-4 w-4" /> {session?.name ?? "Session"}
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight">Attendance</h1>
      </div>

      <RollCall
        rows={meeting.roster}
        marks={marks}
        onChange={setMarks}
        showLateMinutes
        rollMode={rollMode}
        onRollMode={setRollMode}
      />

      {/* Sticky save — one thumb, one tap. Sits above the mobile bottom-tab bar
          (h-16) and clears the desktop sidebar; pads for the home indicator. */}
      <div className="fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-30 border-t border-border bg-card/95 px-4 pt-3 pb-3 backdrop-blur lg:bottom-0 lg:z-40 lg:pl-64 lg:pb-3">
        <div className="mx-auto flex max-w-2xl items-center gap-3">
          <p className="shrink-0 text-xs text-muted-foreground">
            {counts.present}/{counts.total} present
            {counts.absent ? ` · ${counts.absent} absent` : ""}
            {counts.late ? ` · ${counts.late} late` : ""}
          </p>
          <Button className="flex-1" disabled={save.isPending || counts.total === 0}
            onClick={() => save.mutate(marks)}>
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
