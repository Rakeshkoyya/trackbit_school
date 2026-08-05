"use client";

/**
 * The exam workbench (founder, 2026-08-05) — pick a class and a subject, record
 * a test, and read every previous one underneath.
 *
 * It replaces the old scores landing, which was a grid of class tiles over a
 * flat feed. Two things were wrong with that and both are about the same
 * omission — the **subject**:
 *
 *   · she picked a class and then had to pick her subject again inside the
 *     capture form, from a dropdown of every subject in the school, including
 *     the ones that are not hers. The server refuses those now
 *     (`assert_can_record_subject`), so offering them was offering a refusal.
 *   · the feed was `limit`-capped and unfiltered, so the 31st test of the term
 *     was unreachable from any screen, and "how did 6-B do in Hindi this term"
 *     could not be asked at all.
 *
 * Mounted twice, over the same component and the same endpoints:
 *
 *   Students → Academics → Exams   every class-subject she teaches
 *   ABC bands → Exams              only the MONITORED class-subjects, with the
 *                                  type pinned to the band test
 *
 * The second is deliberately the same screen rather than a band-specific one. A
 * band test is an exam — `D-76` promotes a locked exam to one — and a separate
 * capture surface would be a second place for a child's mark to live.
 *
 * Scope is the CALLER's to supply and the server's to enforce: this component
 * renders whatever list it is handed and never widens it.
 */

import { useQuery } from "@tanstack/react-query";
import {
  ChevronLeft, ChevronRight, ClipboardList, Lock, Plus, Users, X,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { ExamCapture } from "@/components/school/exam-capture";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";
import type { CycleType, ExamSummary } from "@/lib/school-types";
import { cn } from "@/lib/utils";

/** One class the caller may record in, and which of its subjects are theirs. */
export interface WorkbenchClass {
  class_id: string;
  class_label: string;
  subjects: { id: string; label: string }[];
}

const fmtDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN",
    { day: "2-digit", month: "short", year: "2-digit" });

const chip = (active: boolean) =>
  cn("whitespace-nowrap rounded-full border px-3 py-1.5 text-sm font-medium transition-colors",
    active ? "border-primary bg-primary text-primary-foreground"
      : "border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground");

function ExamRow({ exam }: { exam: ExamSummary }) {
  return (
    <Link href={`/students/academics/exams/exam/${exam.id}`}
      className="grid grid-cols-[1fr_auto] items-center gap-3 px-4 py-2.5 transition-colors hover:bg-muted/40">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="truncate text-[13px] font-semibold">{exam.name}</span>
          {exam.type_label ? <Badge tone="neutral">{exam.type_label}</Badge> : null}
          {exam.locked ? (
            <Badge tone="success"><Lock className="h-3 w-3" /> locked</Badge>
          ) : null}
          {exam.few_students ? (
            <Badge tone="warning">
              <Users className="h-3 w-3" /> {exam.roster_count} students
            </Badge>
          ) : null}
        </div>
        <p className="mt-0.5 truncate font-mono text-[10px] text-muted-foreground">
          {fmtDay(exam.date)}
          {exam.class_label ? ` · ${exam.class_label}` : " · all classes"}
          {exam.subject_name ? ` · ${exam.subject_name}` : ""}
          {exam.total_marks ? ` · out of ${exam.total_marks}` : ""}
          {/* `S-114`: which bucket it sits in. Nothing downstream ever adds a
              slip test to a term paper, and the row says which this is. */}
          {exam.scale === "major" ? " · major" : ""}
          {exam.created_by_name ? ` · ${exam.created_by_name}` : ""}
        </p>
      </div>
      <div className="shrink-0 text-right font-mono text-[11px] tabular-nums">
        {exam.avg_pct != null ? (
          <>
            <span className="block text-[15px]">{exam.avg_pct}%</span>
            <span className="block text-[10px] text-muted-foreground">
              {exam.scored_count}
              {exam.roster_count ? ` of ${exam.roster_count}` : ""} marked
            </span>
          </>
        ) : (
          // Never a 0% — no marks is a state of the record, not a result.
          <span className="text-[10px] text-muted-foreground">no marks yet</span>
        )}
      </div>
    </Link>
  );
}

export function ExamWorkbench({ classes, isLoading, fixedType, emptyScopeText,
  captureHint }: {
  classes: WorkbenchClass[];
  isLoading?: boolean;
  /** Pins the exam kind — the bands mounting records band tests. */
  fixedType?: CycleType;
  emptyScopeText: string;
  captureHint?: string;
}) {
  const router = useRouter();
  const [classId, setClassId] = useState<string | null>(null);
  const [subjectId, setSubjectId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [recording, setRecording] = useState(false);

  const klass = classes.find((c) => c.class_id === classId) ?? classes[0] ?? null;
  const subject = klass?.subjects.find((s) => s.id === subjectId)
    ?? (subjectId ? undefined : klass?.subjects[0]);

  const { data, isLoading: feedLoading } = useQuery({
    queryKey: ["exam-feed-page", klass?.class_id ?? null, subject?.id ?? null, page],
    queryFn: () => schoolApi.examFeedPage({
      classId: klass?.class_id, subjectId: subject?.id, page, size: 15,
    }),
    enabled: !!klass,
  });

  if (isLoading) return <PageLoading label="Loading your classes…" />;

  if (!classes.length) {
    return (
      <p className="rounded-xl border border-dashed border-border px-4 py-10 text-center text-sm text-muted-foreground">
        <ClipboardList className="mx-auto mb-2 h-6 w-6" />
        {emptyScopeText}
      </p>
    );
  }

  const pages = data ? Math.max(1, Math.ceil(data.total / data.size)) : 1;
  const pick = (id: string) => {
    setClassId(id);
    setSubjectId(null);
    setPage(1);
    setRecording(false);
  };

  return (
    <div>
      {/* 1 · class, then subject. Both are chips rather than dropdowns: a
             teacher has two or three of each, and the set IS the information —
             a closed select hides how little of the school is hers. */}
      <div className="mb-2 flex flex-wrap gap-1.5">
        {classes.map((c) => (
          <button key={c.class_id} type="button"
            className={chip(c.class_id === klass?.class_id)}
            onClick={() => pick(c.class_id)}>
            {c.class_label}
          </button>
        ))}
      </div>
      {klass && klass.subjects.length ? (
        <div className="mb-4 flex flex-wrap gap-1.5">
          {klass.subjects.map((s) => (
            <button key={s.id} type="button" className={chip(s.id === subject?.id)}
              onClick={() => { setSubjectId(s.id); setPage(1); setRecording(false); }}>
              {s.label}
            </button>
          ))}
        </div>
      ) : (
        <p className="mb-4 text-[12px] text-muted-foreground">
          You have no subjects in this class to record a test for.
        </p>
      )}

      {/* 2 · record */}
      {klass && subject ? (
        <section className="mb-6 overflow-hidden rounded-xl border border-border bg-card">
          <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-4 py-2.5">
            <span className="min-w-0">
              <span className="block text-sm font-semibold">
                {klass.class_label} · {subject.label}
              </span>
              {captureHint ? (
                <span className="mt-0.5 block text-[11px] text-muted-foreground">
                  {captureHint}
                </span>
              ) : null}
            </span>
            <Button size="sm" variant={recording ? "outline" : "primary"}
              onClick={() => setRecording((v) => !v)}>
              {recording ? <><X className="h-4 w-4" /> Close</>
                : <><Plus className="h-4 w-4" /> Record a test</>}
            </Button>
          </header>
          {recording ? (
            <div className="px-4 py-4">
              {/* The subject is PINNED — she picked it above, and offering a
                  dropdown of every subject in the school would be offering a
                  refusal the server then has to make. */}
              <ExamCapture classId={klass.class_id} fixedSubjectId={subject.id}
                fixedType={fixedType}
                onSaved={(exam) =>
                  router.push(`/students/academics/exams/exam/${exam.id}`)} />
              <p className="mt-3 text-[11px] leading-snug text-muted-foreground">
                Only part of the class sat it?{" "}
                <Link href={`/students/academics/exams/${klass.class_id}`}
                  className="text-primary hover:underline">
                  Pick who sat it first
                </Link>{" "}
                — retests and catch-ups are recorded against just those children,
                so nobody else reads as having missed a paper.
              </p>
            </div>
          ) : null}
        </section>
      ) : null}

      {/* 3 · previous exams, paginated */}
      <h2 className="mb-2 font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
        Previous exams
        {klass ? ` · ${klass.class_label}` : ""}
        {subject ? ` · ${subject.label}` : ""}
      </h2>
      <section className="overflow-hidden rounded-xl border border-border bg-card">
        {feedLoading && !data ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">Loading…</p>
        ) : data?.rows.length ? (
          <div className="divide-y divide-border">
            {data.rows.map((e) => <ExamRow key={e.id} exam={e} />)}
          </div>
        ) : (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            <ClipboardList className="mx-auto mb-2 h-5 w-5" />
            No exams recorded for this subject yet.
          </p>
        )}

        {data && pages > 1 ? (
          <footer className="flex items-center justify-between gap-2 border-t border-border bg-muted/25 px-4 py-2">
            <span className="font-mono text-[10px] tabular-nums text-muted-foreground">
              {data.total} exams · page {data.page} of {pages}
            </span>
            <span className="flex gap-1.5">
              <button type="button" disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="inline-flex h-7 items-center gap-1 rounded-full border border-border px-2.5 text-xs disabled:opacity-40">
                <ChevronLeft className="h-3.5 w-3.5" /> Newer
              </button>
              <button type="button" disabled={page >= pages}
                onClick={() => setPage((p) => p + 1)}
                className="inline-flex h-7 items-center gap-1 rounded-full border border-border px-2.5 text-xs disabled:opacity-40">
                Older <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </span>
          </footer>
        ) : null}
      </section>
    </div>
  );
}
