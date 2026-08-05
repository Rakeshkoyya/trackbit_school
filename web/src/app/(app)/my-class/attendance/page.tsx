"use client";

// My Class → Attendance (founder, 2026-08-05).
//
// Three things on one screen, in the order she needs them: today's state with
// the buttons that clear it, the month register (V1-3's grid, unchanged — it is
// already the right picture), and the way into any past date.
//
// The register itself is `ClassRegister`, mounted here rather than rewritten.
// Taking or correcting a register happens on the shared attendance sheet at
// `/attendance`, which is the one capture surface for the whole school — a
// second one here would be a second way to write the same rows.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, MessageSquare, NotebookPen } from "lucide-react";
import Link from "next/link";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ClassRegister } from "@/components/school/class-register";
import { MyClassShell } from "@/components/school/my-class-shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/page-loading";
import { showApiError } from "@/lib/errors";
import { insightsApi } from "@/lib/insights-api";
import { schoolApi } from "@/lib/school-api";
import type { SchoolTone } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const RULE: Record<SchoolTone, string> = {
  neutral: "bg-muted-foreground/25",
  green: "bg-success",
  amber: "bg-warning",
  red: "bg-danger",
};

const TONE_TEXT: Record<SchoolTone, string> = {
  neutral: "text-muted-foreground",
  green: "text-success",
  amber: "text-warning",
  red: "text-danger",
};

function TodayBlock({ classId }: { classId: string }) {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["my-class", "overview", classId],
    queryFn: () => schoolApi.myClassOverview(classId),
  });
  const remind = useMutation({
    mutationFn: (studentId: string) =>
      insightsApi.action("guardian_reminded", { student_id: studentId }),
    onSuccess: (res) => {
      if (res.already_done) toast.info(res.message);
      else toast.success(res.message);
      qc.invalidateQueries({ queryKey: ["my-class", "overview", classId] });
    },
    onError: (e) => showApiError(e, "Could not send that"),
  });

  if (isLoading) return <PageLoading label="Loading today…" />;
  if (!data) return null;
  const a = data.attendance;

  return (
    <section className="mb-5 overflow-hidden rounded-xl border border-border bg-card">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
        <span className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
          Today
        </span>
        <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
          {new Date(`${a.date}T00:00:00`).toLocaleDateString(undefined,
            { weekday: "short", day: "numeric", month: "short" })}
          {" · "}
          {a.marked ? `${a.periods_marked} of ${a.periods_scheduled || "?"} periods marked`
            : "no register open"}
        </span>
      </header>

      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <p className={cn("min-w-0 flex-1 text-[13px] leading-snug", TONE_TEXT[a.tone])}>
          {a.headline}
        </p>
        {/* One capture surface for the whole school. The class teacher takes it
            at period one; if she is away any teacher of the class can — which is
            why this goes to the shared sheet rather than to a private one only
            this screen knows about. */}
        <Link href="/attendance"
          className="flex h-9 shrink-0 items-center justify-center rounded-md bg-primary px-3 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90">
          {a.marked ? "Open the register" : "Take the register"}
        </Link>
      </div>

      {a.absentees.length ? (
        <ul className="border-t border-border">
          {a.absentees.map((s) => (
            <li key={s.student_id} className="border-t border-border/60 px-4 py-2.5 first:border-t-0">
              <div className="flex flex-wrap items-start gap-2">
                <span className={cn("mt-[5px] h-3 w-[2px] shrink-0 rounded-full", RULE[s.tone])} />
                <span className="min-w-0 flex-1">
                  <Link href={`/students/${s.student_id}`}
                    className="text-[13px] font-medium hover:underline">
                    {s.full_name}
                  </Link>
                  {s.streak > 1 ? (
                    <span className="ml-1.5 align-[2px]">
                      <Badge tone={s.tone === "red" ? "danger" : "warning"}>
                        {s.streak} days
                      </Badge>
                    </span>
                  ) : null}
                  <span className="block text-[11px] leading-snug text-muted-foreground">
                    {s.reason_note || s.reason_code || "nobody has explained this"}
                    {s.guardian_name ? ` · ${s.guardian_name}` : ""}
                  </span>
                </span>
                {s.guardian_phone ? (
                  <a href={`tel:${s.guardian_phone}`}
                    className="shrink-0 font-mono text-xs text-primary hover:underline">
                    {s.guardian_phone}
                  </a>
                ) : null}
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5 pl-[10px]">
                {s.reminded_today ? (
                  <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-success">
                    <CheckCircle2 className="h-3 w-3" /> Reminded today
                  </span>
                ) : (
                  <Button size="sm" variant="outline" className="h-7 px-2 text-xs"
                    disabled={remind.isPending}
                    onClick={() => remind.mutate(s.student_id)}>
                    <MessageSquare className="h-3.5 w-3.5" /> Remind the family
                  </Button>
                )}
                <Link href={`/students/${s.student_id}`}
                  className="inline-flex h-7 items-center gap-1 rounded-md border border-border bg-card px-2 text-xs hover:bg-muted">
                  <NotebookPen className="h-3.5 w-3.5" /> Their file
                </Link>
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {a.month_pct != null ? (
        <p className="border-t border-border bg-muted/25 px-4 py-2 font-mono text-[10px] tracking-wide text-muted-foreground">
          {a.month_pct}% present this month, across the {a.month_marked_days} of{" "}
          {a.month_school_days} school days this class marked.
        </p>
      ) : (
        <p className="border-t border-border bg-muted/25 px-4 py-2 font-mono text-[10px] tracking-wide text-muted-foreground">
          Nothing marked this month yet — there is no percentage to show.
        </p>
      )}
    </section>
  );
}

export default function MyClassAttendancePage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MyClassShell
        title={(k) => `${k.class_label} · attendance`}
        subtitle={() => "Today, the month behind it, and who to ring"}>
        {(k) => (
          <>
            <TodayBlock classId={k.class_id} />
            {/* V1-3's grid, unchanged: student × school day, each cell the day
                status. A row's shape says "every Monday" faster than any
                percentage — and a day nobody marked stays visibly blank. */}
            <ClassRegister classId={k.class_id} />
          </>
        )}
      </MyClassShell>
    </AuthGuard>
  );
}
