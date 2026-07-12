"use client";

/**
 * One saved exam (SC-5) — the feed card opens here. Subject exams reopen in
 * the same capture form for review/edit; org-wide cycles and diagnostics fall
 * back to the score grid (they have no single-subject exam shape).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ScoreGrid, useClassPick } from "@/components/school/assessments";
import { EXAM_TYPE_LABEL, ExamCapture } from "@/components/school/exam-capture";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { PageLoading } from "@/components/ui/page-loading";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { ApiError } from "@/lib/api-client";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

/** Diagnostics / org-wide cycles: the classic grid, one class at a time. */
function GridFallback({ cycleId, canVerify }: { cycleId: string; canVerify: boolean }) {
  const { yearId } = useYear();
  const { classes, classId, setClassId } = useClassPick(yearId);
  const { data: cycles = [] } = useQuery({ queryKey: ["cycles", yearId], queryFn: () => schoolApi.cycles(), enabled: !!yearId });
  const cycle = cycles.find((c) => c.id === cycleId);
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {cycle ? <Badge tone="neutral">{EXAM_TYPE_LABEL[cycle.type] ?? cycle.type}</Badge> : null}
        <select className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm" value={classId} onChange={(e) => setClassId(e.target.value)}>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}{c.section ? `-${c.section}` : ""}</option>)}
        </select>
      </div>
      {classId ? <ScoreGrid cycleId={cycleId} classId={classId} canVerify={canVerify} /> : null}
    </div>
  );
}

function ExamInner() {
  const { cycleId } = useParams<{ cycleId: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { me } = useAuth();
  const isAdmin = me?.org_role === "admin";

  const { data: exam, error } = useQuery({
    queryKey: ["exam", cycleId],
    queryFn: () => schoolApi.exam(cycleId),
    retry: (count, e) => !(e instanceof ApiError) && count < 2,
  });
  const gridOnly = error instanceof ApiError && error.code === "use_grid";

  const verify = useMutation({
    mutationFn: () => schoolApi.verifyScores(cycleId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exam", cycleId] }); qc.invalidateQueries({ queryKey: ["exam-feed"] }); toast.success("Verified"); },
    onError: (e) => showApiError(e, "Could not verify"),
  });
  const remove = useMutation({
    mutationFn: () => schoolApi.deleteCycle(cycleId),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["exam-feed"] }); toast.success("Exam deleted"); router.push("/students/scores"); },
    onError: (e) => showApiError(e, "Could not delete"),
  });

  if (!exam && !error) return <PageLoading />;

  return (
    <div>
      <div className="mb-4 flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-3">
          <Link href="/students/scores" className="rounded-md border border-border bg-card p-2 hover:bg-muted/40">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <PageHeader
            title={exam ? exam.name : "Exam"}
            subtitle={exam
              ? `Class ${exam.class_label} · ${exam.subject_name} · ${exam.date}${exam.avg_pct != null ? ` · average ${exam.avg_pct}%` : ""}`
              : "Score grid"} />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {exam?.verified ? <Badge tone="success"><CheckCircle2 className="h-3 w-3" /> Verified</Badge> : null}
          {isAdmin && exam && !exam.verified ? (
            <Button size="sm" variant="outline" disabled={verify.isPending} onClick={() => verify.mutate()}>
              Verify
            </Button>
          ) : null}
          {isAdmin ? (
            <Button size="sm" variant="outline" disabled={remove.isPending}
              onClick={() => { if (window.confirm("Delete this exam and all its recorded marks?")) remove.mutate(); }}>
              <Trash2 className="h-4 w-4" />
            </Button>
          ) : null}
        </div>
      </div>

      {gridOnly ? (
        <GridFallback cycleId={cycleId} canVerify={isAdmin} />
      ) : exam ? (
        <ExamCapture classId={exam.class_id} examId={exam.id}
          onSaved={() => {
            qc.invalidateQueries({ queryKey: ["exam", cycleId] });
            qc.invalidateQueries({ queryKey: ["exam-feed"] });
          }} />
      ) : (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          This exam could not be loaded.
        </p>
      )}
    </div>
  );
}

export default function ExamPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <ExamInner />
    </AuthGuard>
  );
}
