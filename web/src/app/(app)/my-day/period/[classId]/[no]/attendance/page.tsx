"use client";

// Roll-call attendance — its own page, opened from the period page. First pass:
// every box starts UNCHECKED, the teacher calls out names, checks who answers,
// and saves (unchecked = absent). Re-opening after a save and checking a student
// who was absent asks "were they late?" so a latecomer becomes present-but-late.
// Storage stays capture-by-exception: only absences and lates are written.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckSquare, Loader2, UserCheck } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageLoading } from "@/components/ui/page-loading";
import { Sheet } from "@/components/ui/sheet";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

type Mark = { present: boolean; late: boolean; late_minutes: number | null };

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

  const [marks, setMarks] = useState<Record<string, Mark> | null>(null);
  const [lateAsk, setLateAsk] = useState<{ studentId: string; name: string } | null>(null);
  const [lateMin, setLateMin] = useState("");

  // Seed once per loaded sheet: marked sheet → current truth; fresh sheet → all
  // unchecked, ready for the roll call.
  if (sheet && marks === null) {
    setMarks(Object.fromEntries(sheet.roster.map((r) => [r.student_id, {
      present: sheet.marked ? r.status !== "absent" : false,
      late: r.status === "late",
      late_minutes: r.late_minutes,
    }])));
  }

  const save = useMutation({
    mutationFn: () => schoolApi.markAttendance({
      class_id: classId, period_no: periodNo,
      exceptions: Object.entries(marks!).flatMap(
        ([student_id, m]): { student_id: string; status: "absent" | "late"; late_minutes?: number | null }[] => {
          if (!m.present) return [{ student_id, status: "absent" }];
          if (m.late) return [{ student_id, status: "late", late_minutes: m.late_minutes }];
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

  const toggle = (studentId: string, name: string) => {
    const m = marks[studentId];
    if (m.present) {
      // Uncheck → absent (also clears a late flag).
      setMarks({ ...marks, [studentId]: { present: false, late: false, late_minutes: null } });
    } else if (sheet.marked) {
      // Attendance was already saved once — a latecomer just walked in.
      setLateMin("");
      setLateAsk({ studentId, name });
    } else {
      setMarks({ ...marks, [studentId]: { present: true, late: false, late_minutes: null } });
    }
  };

  const resolveLate = (late: boolean) => {
    if (!lateAsk) return;
    setMarks({
      ...marks,
      [lateAsk.studentId]: {
        present: true, late,
        late_minutes: late && lateMin ? Number(lateMin) : null,
      },
    });
    setLateAsk(null);
  };

  const presentCount = Object.values(marks).filter((m) => m.present).length;
  const total = sheet.roster.length;

  return (
    <div className="mx-auto max-w-2xl pb-8">
      <Link href={`/my-day/period/${classId}/${periodNo}`}
        className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> P{periodNo} · {sheet.class_label}
      </Link>
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Attendance</h1>
        <Badge tone={presentCount === total ? "success" : "warning"}>{presentCount}/{total} present</Badge>
      </div>
      <p className="mb-4 text-sm text-muted-foreground">
        Call out each name and tick who answers. Unticked students are saved as absent.
        {sheet.marked ? " Ticking someone who was absent will ask if they came late." : ""}
      </p>

      {total === 0 ? (
        <p className="rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground">
          No students on this class’s roster yet.
        </p>
      ) : (
        <>
          <div className="mb-2 flex justify-end">
            <Button size="sm" variant="ghost"
              onClick={() => setMarks(Object.fromEntries(sheet.roster.map((r) => [
                r.student_id,
                marks[r.student_id]?.present
                  ? marks[r.student_id]
                  : { present: true, late: false, late_minutes: null },
              ])))}>
              <CheckSquare className="h-4 w-4" /> Tick everyone
            </Button>
          </div>
          <div className="mb-4 grid gap-1 sm:grid-cols-2">
            {sheet.roster.map((r) => {
              const m = marks[r.student_id];
              return (
                <button key={r.student_id} type="button"
                  onClick={() => toggle(r.student_id, r.full_name)}
                  className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-sm active:scale-[0.99] ${m.present ? "border-[color:var(--success,#234a37)]/40 bg-[color:var(--success,#234a37)]/5" : "border-border bg-card"}`}>
                  <span className={`grid h-5 w-5 shrink-0 place-items-center rounded border ${m.present ? "border-[color:var(--success,#234a37)] bg-[color:var(--success,#234a37)] text-white" : "border-border bg-background"}`}>
                    {m.present ? <UserCheck className="h-3.5 w-3.5" /> : null}
                  </span>
                  <span className="min-w-0 flex-1 truncate">
                    {r.roll_no ? `${r.roll_no}. ` : ""}{r.full_name}
                  </span>
                  {m.late ? <Badge tone="warning">late{m.late_minutes ? ` ${m.late_minutes}m` : ""}</Badge> : null}
                </button>
              );
            })}
          </div>
          <Button className="w-full" disabled={save.isPending} onClick={() => save.mutate()}>
            {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserCheck className="h-4 w-4" />}
            {save.isPending ? "Saving…" : `Save attendance — ${presentCount}/${total} present`}
          </Button>
        </>
      )}

      <Sheet open={!!lateAsk} onOpenChange={(v) => { if (!v) setLateAsk(null); }}
        title={lateAsk ? `${lateAsk.name} just arrived?` : ""}>
        <p className="mb-3 text-sm text-muted-foreground">
          They were marked absent. Mark them present — were they late?
        </p>
        <div className="mb-3">
          <label className="text-xs text-muted-foreground">Minutes late (optional)</label>
          <Input type="number" placeholder="e.g. 10" value={lateMin}
            onChange={(e) => setLateMin(e.target.value)} />
        </div>
        <div className="flex gap-2">
          <Button className="flex-1" onClick={() => resolveLate(true)}>Present — late</Button>
          <Button className="flex-1" variant="outline" onClick={() => resolveLate(false)}>Present — on time</Button>
        </div>
      </Sheet>
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
