"use client";

// My Class → Syllabus (`D-15` / `S-28`, given its own tab 2026-08-05).
//
// **All** subjects her class takes, not just hers, with the subject teacher
// named beside each — she cannot act on it otherwise, and she is staff (`Q-20`).
// Scoped to her own class and nothing wider: there is no school-wide form of
// this view, by design.
//
// The numbers come from exactly the two places the admin board reads
// (`PlannerService.forecast_org` for pace, `CoverageReader` for coverage), so a
// class teacher and her principal can never see different figures for the same
// subject — the `S-51` defect V1-6 existed to remove. What differs between the
// two screens is which rows you may see, never how a row is computed.
//
// The honesty guards ride along: numbers beside a name, framed as needing
// support, **never a rank** — and no pace figure from here ever reaches a
// parent (`D-11`).

import { useQuery } from "@tanstack/react-query";

import { AuthGuard } from "@/components/auth/auth-guard";
import { MyClassShell } from "@/components/school/my-class-shell";
import { SubjectPaceList } from "@/components/school/subject-pace-list";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";

function SyllabusInner({ classId }: { classId: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ["planner", "class-syllabus", classId],
    queryFn: () => schoolApi.classSyllabus(classId),
  });
  if (isLoading) return <PageLoading label="Loading the syllabus…" />;
  if (!data) return null;

  return (
    <div>
      <p className="mb-4 text-[15px] font-medium leading-snug">{data.headline}</p>
      <SubjectPaceList rows={data.rows} showTeacher
        emptyText="This class has no subjects set up yet — an admin adds them in Setup → Academics." />
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
        subtitle={() => "Every subject this class takes, and how far each has got"}>
        {(k) => <SyllabusInner classId={k.class_id} />}
      </MyClassShell>
    </AuthGuard>
  );
}
