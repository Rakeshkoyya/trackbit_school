"use client";

// My Class → Syllabus (`D-15` / `S-28`; rebuilt as the full board 2026-08-05).
//
// **All** subjects her class takes, not just hers, with the subject teacher
// named beside each — she cannot act on it otherwise, and she is staff (`Q-20`).
//
// Founder 2026-08-05, and the two halves of the change belong together: Plan →
// Syllabus no longer folds her homeroom in (there it is *her teaching*, and her
// class's other five subjects are somebody else's plan drowning her own rows),
// and in exchange this tab stops being a five-line pace list and becomes the
// whole SY-1 chapter table. A class teacher asked "where is Hindi?" needs
// **which** chapter, when it was due and when it was taught — which is a table,
// not a percentage.
//
// It is the same `SyllabusTable` the Plan tab renders over the same
// `SyllabusBoardService.board`, so a class teacher and her principal can never
// see different figures for the same chapter — the `S-51` defect V1-6 existed
// to remove. What differs between the two screens is which rows you may see,
// never how a row is computed.
//
// The pace list stays above it as the summary — one line per subject with its
// teacher and its cause-of-behind — because "is Maths moving?" and "which
// chapter is late?" are two questions and the table answers only the second.
//
// The honesty guards ride along: numbers beside a name, framed as needing
// support, **never a rank** — and no pace figure from here ever reaches a
// parent (`D-11`).

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { MyClassShell } from "@/components/school/my-class-shell";
import { SubjectPaceList } from "@/components/school/subject-pace-list";
import { SyllabusTable } from "@/components/school/syllabus-table";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";

function SyllabusInner({ classId }: { classId: string }) {
  const qc = useQueryClient();
  const [term, setTerm] = useState("");

  const { data: pace } = useQuery({
    queryKey: ["planner", "class-syllabus", classId],
    queryFn: () => schoolApi.classSyllabus(classId),
  });
  const { data: board, isLoading } = useQuery({
    queryKey: ["my-class", "syllabus-board", classId, term],
    queryFn: () => schoolApi.myClassSyllabus(classId, term || undefined),
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["my-class", "syllabus-board"] });
    qc.invalidateQueries({ queryKey: ["planner", "class-syllabus"] });
  };

  if (isLoading && !board) return <PageLoading label="Loading the syllabus…" />;

  return (
    <div>
      {pace ? (
        <>
          <p className="mb-3 text-[15px] font-medium leading-snug">{pace.headline}</p>
          <SubjectPaceList rows={pace.rows} showTeacher
            emptyText="This class has no subjects set up yet — an admin adds them in Setup → Academics." />
        </>
      ) : null}

      {board && board.classes.length ? (
        <section className="mt-6">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-mono text-[10px] font-medium uppercase tracking-[0.14em] text-muted-foreground">
              Every chapter, where it stands
            </h2>
            {board.terms.length > 1 ? (
              <select value={term} onChange={(e) => setTerm(e.target.value)}
                aria-label="Term"
                className="rounded-md border border-border bg-card px-2.5 py-1.5 text-sm">
                <option value="">All terms</option>
                {board.terms.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            ) : null}
          </div>
          {/* Grouped by subject, not class: there is exactly one class here, so
              grouping by it would be a single heading over the whole table. */}
          <p className="mb-3 text-[13px] leading-snug text-muted-foreground">
            {board.headline}
          </p>
          {/* `canEdit` is the SERVER's call per chapter — it lets a subject's
              own teacher annotate her chapter and refuses anyone else, so this
              is not an admin act being handed to a class teacher. */}
          <SyllabusTable board={board} canEdit onChanged={refresh}
            defaultGroupBy="subject" />
        </section>
      ) : null}

      <p className="mt-3 text-[11px] leading-snug text-muted-foreground">
        Where a subject is behind, the reason is beside it — whether nobody has
        recorded a lesson, periods were lost to the calendar, chapters were never
        sized, or the teaching is genuinely slower. Those are four different
        conversations and only the last one is about a person.
      </p>
    </div>
  );
}

export default function MyClassSyllabusPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <MyClassShell
        title={(k) => `${k.class_label} · syllabus`}
        subtitle={() => "Every subject this class takes, chapter by chapter"}>
        {(k) => <SyllabusInner classId={k.class_id} />}
      </MyClassShell>
    </AuthGuard>
  );
}
