"use client";

// Taking one class's register, from the board (founder, 2026-08-05).
//
// The SAME capture as the My Day period card: `RollCall`, everyone present by
// default, tap only the exceptions (P1v2), and `markAttendance` writing the same
// exception rows. V1-3's `S-12` rule is one roll-call component and one default,
// so the same act has the same habit everywhere — a second sheet here would be a
// second way to write the same rows and, eventually, a second set of rules about
// what a tap means.
//
// What this page adds over the period card is the two things the covering
// teacher needs: a **date** (a register missed on Tuesday is taken on Wednesday)
// and a **period** she can choose, because the period she is standing in is not
// the one the class teacher would have used.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Loader2, UserCheck } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import {
  RollCall, emptyMarks, marksFrom, rollCounts, type RollMarks,
} from "@/components/school/roll-call";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/page-loading";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import { cn } from "@/lib/utils";

function CaptureInner() {
  const { classId } = useParams<{ classId: string }>();
  const params = useSearchParams();
  const router = useRouter();
  const qc = useQueryClient();

  const day = params.get("date") ?? undefined;
  const [periodNo, setPeriodNo] = useState(() => Number(params.get("period") ?? 1) || 1);
  const [marks, setMarks] = useState<RollMarks | null>(null);
  const [seeded, setSeeded] = useState<string | null>(null);
  const [rollMode, setRollMode] = useState(false);

  const { data: sheet, isLoading } = useQuery({
    queryKey: ["attendance-roster", classId, periodNo, day ?? "today"],
    queryFn: () => schoolApi.attendanceRoster(classId, periodNo, day),
  });

  // Re-seed whenever the period or the date changes, not just once: switching
  // period must not carry the previous period's taps across.
  const key = `${periodNo}:${day ?? "today"}`;
  if (sheet && seeded !== key) {
    setMarks(sheet.marked
      ? marksFrom(sheet.roster, (r) => {
        const row = sheet.roster.find((x) => x.student_id === r.student_id);
        return { status: row?.status, late_minutes: row?.late_minutes };
      })
      : emptyMarks(sheet.roster));
    setSeeded(key);
  }

  const save = useMutation({
    mutationFn: () => schoolApi.markAttendance({
      class_id: classId, period_no: periodNo, date: day ?? null,
      exceptions: Object.entries(marks!).flatMap(
        ([student_id, mk]): {
          student_id: string; status: "absent" | "late"; late_minutes?: number | null;
        }[] => {
          if (mk.status === "absent") return [{ student_id, status: "absent" }];
          if (mk.status === "late") {
            return [{ student_id, status: "late", late_minutes: mk.late_minutes }];
          }
          return [];
        }),
    }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ["attendance"] });
      qc.invalidateQueries({ queryKey: ["attendance-roster"] });
      qc.invalidateQueries({ queryKey: ["my-class"] });
      qc.invalidateQueries({ queryKey: ["my-day"] });
      qc.invalidateQueries({ queryKey: ["insights", "presence"] });
      const alerted = res.alerted_count > 0
        ? ` · ${res.alerted_count} ${res.alerted_count === 1 ? "family" : "families"} told`
        : "";
      toast.success(
        `Saved · ${res.present_count}/${res.roster_count} present${alerted}`);
      router.push("/attendance");
    },
    onError: (e) => showApiError(e, "Could not save attendance"),
  });

  if (isLoading || !sheet || marks === null) return <PageLoading label="Loading roster…" />;
  const counts = rollCounts(marks);

  return (
    <div className="mx-auto max-w-2xl pb-8">
      <Link href="/attendance"
        className="mb-2 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-4 w-4" /> All my classes
      </Link>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          {sheet.class_label}
        </h1>
        <Badge tone={counts.absent === 0 ? "success" : "warning"}>
          {counts.present}/{counts.total} present
        </Badge>
      </div>

      <p className="mb-3 font-mono text-[11px] tracking-wide text-muted-foreground">
        {new Date(`${sheet.date}T00:00:00`).toLocaleDateString(undefined,
          { weekday: "long", day: "numeric", month: "long" })}
        {sheet.marked ? " · already marked — saving replaces it" : " · not marked yet"}
      </p>

      {/* Which period this register is filed against.
          Once a day, there is no such question — the register belongs to the
          DAY, the server files it on whichever period holds it, and offering a
          picker would invite a teacher to open a second one. Every period: the
          picker stays, because there the register genuinely is the period's and
          the one she is standing in is not necessarily the suggested one. */}
      {sheet.once_per_day ? (
        <p className="mb-4 rounded-lg border border-border bg-muted/25 px-3 py-2 text-[11px] leading-snug text-muted-foreground">
          Your school takes <span className="font-medium">one register a day</span>.
          This is today&rsquo;s — whoever takes it, and whenever. Saving replaces it
          rather than adding a second.
        </p>
      ) : (
        <div className="mb-4">
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
            Period
          </span>
          <div className="flex flex-wrap gap-1.5">
            {[1, 2, 3, 4, 5, 6, 7, 8].map((n) => (
              <button key={n} type="button" onClick={() => setPeriodNo(n)}
                className={cn("h-9 w-9 rounded-md border text-sm tabular-nums",
                  n === periodNo
                    ? "border-primary bg-primary/10 font-medium" : "border-border")}>
                {n}
              </button>
            ))}
          </div>
        </div>
      )}

      <RollCall rows={sheet.roster} marks={marks} onChange={setMarks}
        rollMode={rollMode} onRollMode={setRollMode} />

      {sheet.roster.length > 0 ? (
        <Button className="mt-4 w-full" disabled={save.isPending}
          onClick={() => save.mutate()}>
          {save.isPending
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <UserCheck className="h-4 w-4" />}
          {save.isPending
            ? "Saving…"
            : counts.absent === 0 && counts.late === 0
              ? `Save — all ${counts.total} present`
              : `Save — ${counts.present}/${counts.total} present`}
        </Button>
      ) : (
        <p className="mt-4 rounded-lg border border-border bg-card px-4 py-6 text-center text-sm text-muted-foreground">
          Nobody is on this class&rsquo;s roll yet.
        </p>
      )}
    </div>
  );
}

export default function AttendanceCapturePage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <Suspense fallback={<PageLoading label="Loading roster…" />}>
        <CaptureInner />
      </Suspense>
    </AuthGuard>
  );
}
