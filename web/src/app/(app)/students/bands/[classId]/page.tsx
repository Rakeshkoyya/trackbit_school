"use client";

/**
 * Assess one class, for one subject (V1-9, `D-70`/`D-75`).
 *
 * This screen is **entry** (`S-185`): it files a class into A/B/C the first
 * time, either from a test's marks or from the teacher's own assessment against
 * the descriptors. After that, a child changes band on a **band test or a
 * promoted test** — a teacher's action on the exam screen — which is what makes
 * every subsequent band row evidenced without anyone remembering to attach
 * evidence.
 *
 * The subject picker only offers **monitored** subjects (`D-68`): a subject the
 * school does not monitor has no bands and no programme, and is absent rather
 * than shown as an empty column.
 */

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { BandAssess } from "@/components/school/band-assess";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

function AssessInner() {
  const { classId } = useParams<{ classId: string }>();
  const { yearId } = useYear();
  const [subjectId, setSubjectId] = useState("");
  const [cycleId, setCycleId] = useState("");

  const { data: classes = [] } = useQuery({
    queryKey: ["classes", yearId], queryFn: () => schoolApi.classes(yearId!), enabled: !!yearId });
  const { data: setup = [] } = useQuery({ queryKey: ["band-setup"], queryFn: schoolApi.bandSetup });
  const { data: terms = [] } = useQuery({
    queryKey: ["terms", yearId], queryFn: () => schoolApi.terms(yearId ?? undefined),
    enabled: !!yearId });
  const { data: exams = [] } = useQuery({
    queryKey: ["exam-feed", classId], queryFn: () => schoolApi.examFeed({ classId }) });

  const klass = classes.find((c) => c.id === classId);
  const label = klass ? `${klass.name}${klass.section ? `-${klass.section}` : ""}` : "";
  const monitored = setup.filter((s) => s.monitored);
  const effSubject = monitored.some((s) => s.subject_id === subjectId)
    ? subjectId : (monitored[0]?.subject_id ?? "");
  // Only locked exams may pre-fill an assessment — an unverified transcription
  // must not decide a child's support tier (`S-184`).
  const usable = exams.filter((e) => e.locked && e.subject_id === effSubject && !e.grid_only);
  const termId = terms[0]?.id ?? null;

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <Link href="/students/bands" className="rounded-md border border-border bg-card p-2 hover:bg-muted/40">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <PageHeader title={label ? `Assess ${label}` : "Assess a class"}
          subtitle="One subject at a time — a band belongs to a subject, not to a child" />
      </div>

      {!monitored.length ? (
        <p className="rounded-xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          No subjects are being monitored yet. Turn them on in Setup → Settings — a subject
          that isn&apos;t monitored has no bands and no support programme.
        </p>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-end gap-4 rounded-xl border border-border bg-card p-4">
            <div>
              <p className="mb-1 text-xs font-medium">Subject</p>
              <div className="flex flex-wrap gap-1.5">
                {monitored.map((s) => (
                  <button key={s.subject_id} type="button"
                    onClick={() => { setSubjectId(s.subject_id); setCycleId(""); }}
                    className={`rounded-md border px-3 py-1.5 text-sm transition ${
                      s.subject_id === effSubject
                        ? "border-primary bg-primary/10 font-medium text-primary"
                        : "border-border hover:bg-muted/40"}`}>
                    {s.subject_name}
                  </button>
                ))}
              </div>
            </div>
            <div className="min-w-[15rem] flex-1">
              <p className="mb-1 text-xs font-medium">From a test</p>
              <select className="w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
                value={cycleId} onChange={(e) => setCycleId(e.target.value)}>
                <option value="">my own assessment (nothing pre-filled)</option>
                {usable.map((e) => (
                  <option key={e.id} value={e.id}>{e.name} · {e.date}</option>
                ))}
              </select>
              {!usable.length ? (
                <p className="mt-1 text-xs text-muted-foreground">
                  No locked test for this subject yet — assess against the descriptors.
                </p>
              ) : null}
            </div>
          </div>

          {effSubject ? (
            <BandAssess classId={classId} subjectId={effSubject} termId={termId}
              cycleId={cycleId || undefined} />
          ) : null}
        </div>
      )}
    </div>
  );
}

export default function AssessClassPage() {
  return (
    <AuthGuard requireRole="admin">
      <AssessInner />
    </AuthGuard>
  );
}
