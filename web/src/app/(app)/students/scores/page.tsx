"use client";

/**
 * Scores landing (SC-5) — pick a class to record a test, scroll the feed of
 * previous exams below. Teachers see the classes they teach; the admin sees
 * all. Each feed card opens the saved exam for review/edit.
 */

import { useQuery } from "@tanstack/react-query";
import { Camera, ChevronRight, ClipboardList, GraduationCap, Plus, Users } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { NewCycleSheet } from "@/components/school/assessments";
import { EXAM_TYPE_LABEL } from "@/components/school/exam-capture";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { useAuth } from "@/contexts/auth-context";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";
import type { ExamSummary } from "@/lib/school-types";

function ExamPost({ exam }: { exam: ExamSummary }) {
  return (
    <Link href={`/students/scores/exam/${exam.id}`}
      className="flex items-center gap-4 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-muted/40 active:scale-[0.995]">
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <p className="text-sm font-semibold">{exam.name}</p>
          <Badge tone="neutral">{EXAM_TYPE_LABEL[exam.type] ?? exam.type}</Badge>
          {exam.class_label ? <Badge tone="neutral">{exam.class_label}</Badge> : <Badge tone="neutral">All classes</Badge>}
          {exam.subject_name ? <Badge tone="neutral">{exam.subject_name}</Badge> : null}
          {exam.few_students ? <Badge tone="warning"><Users className="h-3 w-3" /> {exam.roster_count} students</Badge> : null}
        </div>
        <p className="mt-1 truncate text-xs text-muted-foreground">
          {exam.date}
          {exam.topic ? ` · ${exam.topic}` : ""}
          {exam.total_marks ? ` · out of ${exam.total_marks}` : ""}
          {exam.created_by_name ? ` · by ${exam.created_by_name}` : ""}
          {exam.page_count ? ` · ${exam.page_count} photo${exam.page_count === 1 ? "" : "s"}` : ""}
        </p>
        <p className="mt-1.5 text-xs text-muted-foreground">
          <span className="font-medium text-foreground">{exam.scored_count}</span>
          {exam.roster_count ? `/${exam.roster_count}` : ""} marks recorded
          {exam.verified ? " · verified" : ""}
        </p>
      </div>
      <div className="shrink-0 text-right">
        {exam.avg_pct != null ? (
          <>
            <p className="text-2xl font-bold tabular-nums">{exam.avg_pct}%</p>
            <p className="text-[11px] text-muted-foreground">class average</p>
          </>
        ) : (
          <p className="text-xs text-muted-foreground">no marks yet</p>
        )}
      </div>
      <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
    </Link>
  );
}

function ScoresInner() {
  const { me } = useAuth();
  const isAdmin = me?.org_role === "admin";
  const { yearId } = useYear();
  const [newCycle, setNewCycle] = useState(false);

  const { data: classes = [] } = useQuery({
    queryKey: ["classes", yearId, !isAdmin],
    queryFn: () => schoolApi.classes(yearId!, !isAdmin),
    enabled: !!yearId,
  });
  const { data: terms = [] } = useQuery({ queryKey: ["terms", yearId], queryFn: () => schoolApi.terms(yearId ?? undefined), enabled: !!yearId });
  const { data: feed = [], isLoading } = useQuery({ queryKey: ["exam-feed"], queryFn: () => schoolApi.examFeed({ limit: 30 }) });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <PageHeader title="Scores" subtitle="Record a test's results, browse previous exams" />
        <div className="flex items-center gap-2">
          <YearSwitcher />
          {isAdmin ? (
            <Button size="sm" variant="outline" onClick={() => setNewCycle(true)}>
              <Plus className="h-4 w-4" /> New cycle
            </Button>
          ) : null}
        </div>
      </div>

      {/* 1 · pick a class to record a test */}
      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
        {classes.map((c) => (
          <Link key={c.id} href={`/students/scores/${c.id}`}
            className="flex items-center gap-3 rounded-xl border border-border bg-card p-4 transition-colors hover:bg-muted/40 active:scale-[0.99]">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-md bg-primary/10 text-primary">
              <GraduationCap className="h-5 w-5" />
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold">
                Class {c.name}{c.section ? `-${c.section}` : ""}
              </span>
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Camera className="h-3 w-3" /> record a test
              </span>
            </span>
          </Link>
        ))}
        {classes.length === 0 ? (
          <p className="col-span-full rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
            {isAdmin ? "No classes in this year yet — set them up first." : "No classes assigned to you yet."}
          </p>
        ) : null}
      </div>

      {/* 2 · previous exams */}
      <h2 className="mb-2 text-sm font-semibold text-muted-foreground">Previous exams</h2>
      <div className="space-y-2.5">
        {feed.map((exam) => <ExamPost key={exam.id} exam={exam} />)}
        {!isLoading && feed.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            <ClipboardList className="mx-auto mb-2 h-6 w-6" /> No exams recorded yet — tap a class above to record the first one.
          </p>
        ) : null}
      </div>

      <NewCycleSheet open={newCycle} onOpenChange={setNewCycle} termId={terms[0]?.id ?? null} yearId={yearId} />
    </div>
  );
}

export default function ScoresPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <ScoresInner />
    </AuthGuard>
  );
}
