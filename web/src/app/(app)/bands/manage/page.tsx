"use client";

/**
 * ABC bands → Manage bands.
 *
 * Two tab rows — class, then subject — over one table of children. Same screen
 * for both roles, different contents: `GET /bands/scope` returns an admin the
 * whole school and a teacher only the class-subjects she actually takes, so the
 * tabs are built from what she may act on and there is no such thing as a tab
 * that 403s.
 *
 * The band itself is set by `BandAssess`, unchanged from V1-9 — this page is the
 * navigation and the test-entry door around it.
 *
 * **Entry vs movement** (`S-185`), and the reason there are two ways to record a
 * test here rather than one:
 *
 * - *From a test* pre-fills the rows from a locked exam's marks, and she moves
 *   only what she disagrees with (`Q-79`).
 * - *Record a test* opens `ExamCapture` — the photo/PDF pipeline exams already
 *   owns (`D-82`). Marks land as a real exam, which is what makes them
 *   verifiable, lockable and promotable later; bands never grew a private score
 *   store, because a mark that exists in two places is a mark that will disagree
 *   with itself.
 *
 * Once a class is filed, a child *moves* band on a locked test promoted from the
 * exam page — never on a slider here.
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FilePlus2 } from "lucide-react";
import { useMemo, useState } from "react";

import { BandAssess } from "@/components/school/band-assess";
import { ExamCapture } from "@/components/school/exam-capture";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";
import { cn } from "@/lib/utils";

/** The two tab rows. Deliberately not a pair of <select>s: a school has a
 * handful of classes and three monitored subjects, and a dropdown hides the one
 * thing worth seeing — how many are left to do. */
function TabRow({
  items, value, onChange, label,
}: {
  items: { id: string; label: string }[];
  value: string;
  onChange: (id: string) => void;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-14 shrink-0 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </span>
      <div className="flex flex-1 gap-1 overflow-x-auto pb-1">
        {items.map((i) => (
          <button
            key={i.id}
            type="button"
            onClick={() => onChange(i.id)}
            className={cn(
              "whitespace-nowrap rounded-md border px-3 py-1.5 text-sm font-medium transition-colors",
              i.id === value
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border text-muted-foreground hover:bg-muted/40",
            )}
          >
            {i.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function ManageBandsPage() {
  const qc = useQueryClient();
  const { yearId } = useYear();
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [cycleId, setCycleId] = useState("");
  const [recording, setRecording] = useState(false);

  const { data: scope, isLoading } = useQuery({
    queryKey: ["band-scope"],
    queryFn: schoolApi.bandScope,
  });
  const { data: terms = [] } = useQuery({
    queryKey: ["terms", yearId],
    queryFn: () => schoolApi.terms(yearId ?? undefined),
  });
  const termId = terms[0]?.id ?? null;

  // All three selections are DERIVED from state + what the server says exists,
  // never synced back into state by an effect. The three rows are dependent —
  // changing class can invalidate the subject, and changing subject can
  // invalidate the chosen test — and resolving that in effects is a chain of
  // cascading renders where a stale subject is briefly real. Falling back
  // during render means the invalid combination never exists at all.
  const klass = useMemo(
    () => scope?.classes.find((c) => c.class_id === classId) ?? scope?.classes[0],
    [scope, classId],
  );
  const subject = useMemo(
    () => klass?.subjects.find((s) => s.id === subjectId) ?? klass?.subjects[0],
    [klass, subjectId],
  );
  const effSubject = subject?.id ?? "";

  // Locked exams for this class-subject — the `Q-79` pre-fill source.
  const { data: exams = [] } = useQuery({
    queryKey: ["exams", klass?.class_id],
    queryFn: () => schoolApi.examFeed({ classId: klass!.class_id }),
    enabled: !!klass,
  });
  const usable = exams.filter((e) => e.locked && e.subject_id === effSubject && !e.grid_only);
  const effCycle = usable.some((e) => e.id === cycleId) ? cycleId : "";

  if (isLoading) return <div className="h-64 animate-pulse rounded-xl bg-muted" />;

  if (!scope?.enabled) {
    return (
      <div className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
        No subject is being monitored yet. Choose them in Setup → Settings → Support
        programme.
      </div>
    );
  }
  if (!scope.classes.length) {
    return (
      <div className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
        You don&apos;t take any of the monitored subjects, so there is nothing to band
        here.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader
          title="Manage bands"
          subtitle="Assess a class against the descriptors, or pre-fill from a locked test."
        />
        <YearSwitcher />
      </div>

      <div className="space-y-2 rounded-xl border border-border bg-card p-3">
        <TabRow
          label="Class"
          items={scope.classes.map((c) => ({ id: c.class_id, label: c.class_label }))}
          value={klass?.class_id ?? ""}
          onChange={setClassId}
        />
        {klass ? (
          <TabRow
            label="Subject"
            items={klass.subjects}
            value={effSubject}
            onChange={setSubjectId}
          />
        ) : null}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <label className="flex items-center gap-2 text-xs text-muted-foreground">
          Pre-fill from
          <select
            className="rounded-md border border-border bg-card px-2 py-1.5 text-sm"
            value={effCycle}
            onChange={(e) => setCycleId(e.target.value)}
          >
            <option value="">my own assessment</option>
            {usable.map((e) => (
              <option key={e.id} value={e.id}>
                {e.name}
              </option>
            ))}
          </select>
          {!usable.length ? (
            <span>— no locked test for this subject yet</span>
          ) : null}
        </label>
        <Button variant="outline" size="sm" onClick={() => setRecording(true)}>
          <FilePlus2 className="h-4 w-4" /> Record a test
        </Button>
      </div>

      {effSubject && klass ? (
        <BandAssess
          key={`${klass.class_id}-${effSubject}-${effCycle}`}
          classId={klass.class_id}
          subjectId={effSubject}
          termId={termId}
          cycleId={effCycle || undefined}
        />
      ) : null}

      {/* The marks go in as a real exam — photos, PDF or typed — so they can be
          verified, locked and later promoted. Bands keep no private score store. */}
      <Sheet
        open={recording}
        onOpenChange={setRecording}
        title={`Record a test · ${klass?.class_label ?? ""}`}
      >
        {recording && klass ? (
          <ExamCapture
            classId={klass.class_id}
            onSaved={() => {
              qc.invalidateQueries({ queryKey: ["exams"] });
              setRecording(false);
            }}
          />
        ) : null}
      </Sheet>
    </div>
  );
}
