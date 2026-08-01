"use client";

// Roll-call attendance — its own page, opened from the period page.
//
// V1-3 (S-12): ONE roll-call component, ONE default. Everyone starts present
// and the teacher taps only the exceptions (SPRD2 §5.4's "All present ✓, one
// tap"); the old name-by-name flow survives behind "Call the roll". The session
// sheet renders the same component, so the same act has the same habit
// everywhere. Storage is unchanged: capture-by-exception, absences and lates
// only.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, UserCheck } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  RollCall,
  emptyMarks,
  marksFrom,
  rollCounts,
  type RollMarks,
} from "@/components/school/roll-call";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/page-loading";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

function AttendanceInner() {
  const params = useParams<{ classId: string; no: string }>();
  const classId = params.classId;
  const periodNo = Number(params.no);
  const router = useRouter();
  const qc = useQueryClient();

  const { data: sheet, isLoading } = useQuery({
    queryKey: ["attendance-roster", classId, periodNo],
    queryFn: () => schoolApi.attendanceRoster(classId, periodNo),
  });

  const [marks, setMarks] = useState<RollMarks | null>(null);
  const [rollMode, setRollMode] = useState(false);

  // Seed once per loaded sheet: a marked sheet reopens on its recorded truth, a
  // fresh one on "everyone present".
  if (sheet && marks === null) {
    setMarks(sheet.marked
      ? marksFrom(sheet.roster, (r) => {
        const row = sheet.roster.find((x) => x.student_id === r.student_id);
        return { status: row?.status, late_minutes: row?.late_minutes };
      })
      : emptyMarks(sheet.roster));
  }

  const save = useMutation({
    mutationFn: () => schoolApi.markAttendance({
      class_id: classId, period_no: periodNo,
      exceptions: Object.entries(marks!).flatMap(
        ([student_id, m]): { student_id: string; status: "absent" | "late"; late_minutes?: number | null }[] => {
          if (m.status === "absent") return [{ student_id, status: "absent" }];
          if (m.status === "late") return [{ student_id, status: "late", late_minutes: m.late_minutes }];
          return [];
        }),
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["attendance-roster", classId, periodNo] });
      qc.invalidateQueries({ queryKey: ["period-card", classId, periodNo] });
      qc.invalidateQueries({ queryKey: ["my-day"] });
      const alerted = res.alerted_count > 0 ? ` · ${res.alerted_count} parents alerted` : "";
      toast.success(`Attendance saved · ${res.present_count}/${res.roster_count} present${alerted}`);
      router.push(`/my-day/period/${classId}/${periodNo}`);
    },
    onError: (e) => showApiError(e, "Could not save attendance"),
  });

  if (isLoading || !sheet || marks === null) return <PageLoading label="Loading roster…" />;

  const counts = rollCounts(marks);

  return (
    <div className="mx-auto max-w-2xl pb-8">
      <Link href={`/my-day/period/${classId}/${periodNo}`}
        className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> P{periodNo} · {sheet.class_label}
      </Link>
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Attendance</h1>
        <Badge tone={counts.absent === 0 ? "success" : "warning"}>
          {counts.present}/{counts.total} present
        </Badge>
      </div>

      <RollCall
        rows={sheet.roster}
        marks={marks}
        onChange={setMarks}
        rollMode={rollMode}
        onRollMode={setRollMode}
      />

      {sheet.roster.length > 0 ? (
        <Button className="mt-4 w-full" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserCheck className="h-4 w-4" />}
          {save.isPending
            ? "Saving…"
            : counts.absent === 0 && counts.late === 0
              ? `Save — all ${counts.total} present`
              : `Save — ${counts.present}/${counts.total} present`}
        </Button>
      ) : null}
    </div>
  );
}

export default function AttendancePage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <AttendanceInner />
    </AuthGuard>
  );
}
