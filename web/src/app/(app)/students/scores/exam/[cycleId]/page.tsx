"use client";

/**
 * One saved exam — **two tabs** (V1-8, `D-80`).
 *
 *   Score   the roster and their marks, nothing else
 *   Report  the analysis: how the class did, who to talk to, where the marks
 *           were lost, what had actually been taught
 *
 * The header carries the other V1-8 act: **verify & lock** (`D-53`). The teacher
 * who marked the papers locks them; after that the exam *is* the record, and
 * only an admin can reopen it — **with a reason, appended** (`Q-62`), never a
 * silent overwrite of a mark somebody confirmed in July.
 *
 * Org-wide cycles and diagnostics have no single-subject exam shape and still
 * fall back to the score grid.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Lock, LockOpen, Trash2 } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ScoreGrid, useClassPick } from "@/components/school/assessments";
import { EXAM_TYPE_LABEL, ExamCapture } from "@/components/school/exam-capture";
import { BandPromoteCard } from "@/components/school/band-promote";
import { ExamReportView } from "@/components/school/exam-report";
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

function ReportTab({ cycleId }: { cycleId: string }) {
  const { data, error } = useQuery({
    queryKey: ["exam-report", cycleId],
    queryFn: () => schoolApi.examReport(cycleId),
    retry: (count, e) => !(e instanceof ApiError) && count < 2,
  });
  if (error) {
    return (
      <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
        This exam has no single class-subject to report on.
      </p>
    );
  }
  if (!data) return <PageLoading />;
  return <ExamReportView report={data} />;
}

function ExamInner() {
  const { cycleId } = useParams<{ cycleId: string }>();
  const router = useRouter();
  const qc = useQueryClient();
  const { me } = useAuth();
  const isAdmin = me?.org_role === "admin";
  const [tab, setTab] = useState<"score" | "report">("score");

  const { data: exam, error } = useQuery({
    queryKey: ["exam", cycleId],
    queryFn: () => schoolApi.exam(cycleId),
    retry: (count, e) => !(e instanceof ApiError) && count < 2,
  });
  const gridOnly = error instanceof ApiError && error.code === "use_grid";

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["exam", cycleId] });
    qc.invalidateQueries({ queryKey: ["exam-report", cycleId] });
    qc.invalidateQueries({ queryKey: ["exam-feed"] });
  };

  const lock = useMutation({
    mutationFn: () => schoolApi.lockExam(cycleId),
    onSuccess: () => { refresh(); toast.success("Locked — these marks are now the record"); },
    onError: (e) => showApiError(e, "Could not lock"),
  });
  const unlock = useMutation({
    mutationFn: (reason: string) => schoolApi.unlockExam(cycleId, reason),
    onSuccess: () => { refresh(); toast.success("Unlocked — the reason is on the record"); },
    onError: (e) => showApiError(e, "Could not unlock"),
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
              ? `Class ${exam.class_label} · ${exam.subject_name} · ${exam.date}${
                exam.avg_pct != null ? ` · average ${exam.avg_pct}%` : ""}`
              : "Score grid"} />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {exam?.locked ? <Badge tone="success"><Lock className="h-3 w-3" /> Locked</Badge> : null}
          {exam && !exam.locked ? (
            <Button size="sm" disabled={lock.isPending} onClick={() => lock.mutate()}>
              <CheckCircle2 className="h-4 w-4" /> Verify &amp; lock
            </Button>
          ) : null}
          {isAdmin && exam?.locked ? (
            <Button size="sm" variant="outline" disabled={unlock.isPending}
              onClick={() => {
                const reason = window.prompt(
                  "Why is this being unlocked? The reason is kept on the record.");
                if (reason?.trim()) unlock.mutate(reason.trim());
              }}>
              <LockOpen className="h-4 w-4" /> Unlock
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
        <>
          <div className="mb-4 flex items-center gap-1 rounded-lg border border-border bg-card p-1 text-sm">
            {(["score", "report"] as const).map((t) => (
              <button key={t} type="button" onClick={() => setTab(t)}
                className={`flex-1 rounded-md px-3 py-1.5 font-medium capitalize transition ${
                  tab === t ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/40"}`}>
                {t === "score" ? "Score" : "Report"}
              </button>
            ))}
          </div>
          {tab === "score" ? (
            <ExamCapture classId={exam.class_id} examId={exam.id} onSaved={refresh} />
          ) : (
            <ReportTab cycleId={cycleId} />
          )}
          {/* V1-9 (`D-76`): one action at the bottom of a screen she is on
              anyway — this test told her what she needed; it can count. */}
          {tab === "score" && exam.locked ? (
            <div className="mt-4"><BandPromoteCard cycleId={cycleId} /></div>
          ) : null}
          {exam.lock_history.length ? (
            <div className="mt-4 rounded-xl border border-border bg-card p-4">
              <p className="text-sm font-semibold">Lock history</p>
              <ul className="mt-2 space-y-1 text-xs text-muted-foreground">
                {exam.lock_history.map((h, i) => (
                  <li key={i}>
                    <span className="font-medium text-foreground capitalize">{h.action}ed</span>
                    {h.by_name ? ` by ${h.by_name}` : ""} · {String(h.at).slice(0, 10)}
                    {h.reason ? ` — ${h.reason}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </>
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
