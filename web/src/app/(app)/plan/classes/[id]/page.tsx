"use client";

/**
 * Plan → Classes → one class (V2-P10). Everything ingestion stored about it.
 *
 * The column that matters most is "Periods": the weekly budget the admin *entered*
 * on the class-subject, next to the number of slots the timetable actually gives it.
 * These are two independent sources of truth today, and `distribute()` builds every
 * plan date from the entered one. When they disagree, every date for that subject is
 * wrong — and nothing in the product said so until this screen.
 *
 * Syllabus coverage is computed from lesson logs (P2: plan is baseline, log is
 * actual), so it moves on its own as teachers teach.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Loader2,
  Sparkles,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { Rag, SubjectRow } from "@/lib/school-types";

const RAG_TONE: Record<Rag, "success" | "neutral" | "warning" | "danger"> = {
  green: "success",
  none: "neutral",
  amber: "warning",
  red: "danger",
  unplanned: "warning",
  unallocated: "warning",
};

const fmt = (d: string | null) =>
  d ? new Date(d + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : "—";

function Coverage({ s }: { s: SubjectRow }) {
  if (!s.topics) return <span className="text-xs text-muted-foreground">no syllabus</span>;
  const pct = Math.round((s.topics_taught / s.topics) * 100);
  return (
    <div className="min-w-32">
      <div className="h-1.5 overflow-hidden rounded-full bg-muted">
        <motion.div
          className="h-full rounded-full bg-primary"
          initial={{ width: 0 }}
          animate={{ width: `${pct}%` }}
          transition={{ duration: 0.5, ease: "easeOut" }}
        />
      </div>
      <p className="mt-1 text-[11px] text-muted-foreground">
        {s.topics_taught}/{s.topics} topics · {s.chapters} chapters · {s.est_periods} periods
      </p>
    </div>
  );
}

function Periods({ s }: { s: SubjectRow }) {
  if (!s.periods_mismatch) {
    return (
      <span className="text-sm tabular-nums">
        {s.timetabled_periods || s.periods_per_week}
        <span className="text-xs text-muted-foreground">/wk</span>
      </span>
    );
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 text-sm text-warning"
      title="The plan is built from the entered budget, so its dates are wrong."
    >
      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
      <span className="tabular-nums">
        {s.periods_per_week} entered ≠ {s.timetabled_periods} timetabled
      </span>
    </span>
  );
}

function ClassInner({ classId }: { classId: string }) {
  const { me } = useAuth();
  const canEdit = me?.org_role === "admin";
  const qc = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["class-overview", classId],
    queryFn: () => schoolApi.classOverview(classId),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["class-overview", classId] });
    qc.invalidateQueries({ queryKey: ["school-overview"] });
  };

  const generate = useMutation({
    mutationFn: (csId: string) => schoolApi.generatePlan(csId),
    onSuccess: (r) => {
      invalidate();
      if (r.violations.length) {
        toast.warning(r.violations[0].message);
      } else {
        toast.success("Plan generated — every chapter fits, in order, before its exams.");
      }
    },
    onError: (e) => showApiError(e, "Could not generate the plan"),
  });

  const approve = useMutation({
    mutationFn: (csId: string) => schoolApi.approvePlan(csId),
    onSuccess: () => {
      invalidate();
      toast.success("Baseline locked");
    },
    onError: (e) => showApiError(e, "Could not approve the plan"),
  });

  if (isLoading || !data) return <PageHeader title="Class" subtitle="Loading…" />;

  const mismatches = data.subjects.filter((s) => s.periods_mismatch).length;

  return (
    <div>
      <Link
        href="/plan/classes"
        className="mb-3 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> All classes
      </Link>

      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <PageHeader
          title={`Class ${data.label}`}
          subtitle={`${data.year_label} · ${data.students} students${
            data.class_teacher_name ? ` · class teacher ${data.class_teacher_name}` : ""
          }`}
        />
        <div className="flex items-center gap-2">
          <Link href={`/students?class_id=${classId}`}>
            <Button variant="outline" size="sm">
              <UserRound className="h-4 w-4" /> Roster
            </Button>
          </Link>
          <Link href="/plan/timetable">
            <Button variant="outline" size="sm">
              Timetable
            </Button>
          </Link>
        </div>
      </div>

      {mismatches ? (
        <div className="mb-5 flex items-start gap-2 rounded-xl border border-border bg-warning-soft/50 px-4 py-3 text-sm text-warning">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <p>
            {mismatches} subject{mismatches === 1 ? "" : "s"} have a weekly period budget that
            disagrees with the timetable. The plan is built from the entered number, so its dates
            are wrong until you fix one of them.
          </p>
        </div>
      ) : null}

      <div className="overflow-hidden rounded-xl border border-border bg-card">
        <table className="w-full text-sm">
          <thead className="border-b border-border text-left text-xs uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="px-4 py-2.5 font-medium">Subject</th>
              <th className="px-4 py-2.5 font-medium">Teacher</th>
              <th className="px-4 py-2.5 font-medium">Periods</th>
              <th className="px-4 py-2.5 font-medium">Syllabus covered</th>
              <th className="px-4 py-2.5 font-medium">Finishes</th>
              <th className="px-4 py-2.5 font-medium">Plan</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {data.subjects.map((s) => (
              <tr key={s.class_subject_id} className="align-top hover:bg-muted/50">
                <td className="px-4 py-3 font-medium">{s.subject_name}</td>
                <td className="px-4 py-3">
                  {s.teacher_name ?? (
                    <span className="inline-flex items-center gap-1.5 text-xs text-warning">
                      <AlertTriangle className="h-3.5 w-3.5" /> unassigned
                    </span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <Periods s={s} />
                </td>
                <td className="px-4 py-3">
                  <Coverage s={s} />
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {s.plan_status === "none" ? (
                    "—"
                  ) : (
                    <>
                      <div>baseline {fmt(s.baseline_finish)}</div>
                      <div className={s.weeks_behind ? "text-warning" : undefined}>
                        projected {fmt(s.projected_finish)}
                        {s.weeks_behind ? ` (+${s.weeks_behind}w)` : ""}
                      </div>
                    </>
                  )}
                </td>
                <td className="px-4 py-3">
                  <div className="flex flex-col items-start gap-1">
                    <Badge tone={RAG_TONE[s.forecast]}>{s.forecast}</Badge>
                    {s.plan_status === "approved" ? (
                      <span className="inline-flex items-center gap-1 text-[11px] text-muted-foreground">
                        <CheckCircle2 className="h-3 w-3" /> locked
                      </span>
                    ) : s.plan_status === "partial" ? (
                      <span className="text-[11px] text-muted-foreground">some terms locked</span>
                    ) : (
                      <span className="text-[11px] text-muted-foreground">{s.plan_status}</span>
                    )}
                  </div>
                </td>
                <td className="px-4 py-3 text-right">
                  {canEdit ? (
                    <div className="flex justify-end gap-1.5">
                      {/* Whole-year generate/approve can't act on a term-planned
                          subject — the server refuses to rewrite a locked term. Send
                          them to Week plan, which has the per-term controls. */}
                      {s.plan_status !== "approved" && s.plan_status !== "partial" ? (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={!s.topics || generate.isPending}
                            onClick={() => generate.mutate(s.class_subject_id)}
                            title={s.topics ? "" : "Add a syllabus first"}
                          >
                            {generate.isPending ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Sparkles className="h-3.5 w-3.5" />
                            )}
                            Generate
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={s.plan_status === "none" || approve.isPending}
                            onClick={() => approve.mutate(s.class_subject_id)}
                          >
                            Approve
                          </Button>
                        </>
                      ) : (
                        <Link
                          href={`/plan/week?class_subject_id=${s.class_subject_id}`}
                          className="text-xs font-medium text-primary hover:underline"
                        >
                          View plan
                        </Link>
                      )}
                    </div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!data.subjects.length ? (
          <p className="px-4 py-10 text-center text-sm text-muted-foreground">
            No subjects on this class yet — add them in Setup.
          </p>
        ) : null}
      </div>
    </div>
  );
}

export default function ClassDetailPage() {
  const params = useParams<{ id: string }>();
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <ClassInner classId={params.id} />
    </AuthGuard>
  );
}
