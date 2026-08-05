"use client";

/**
 * ABC bands → Exams (founder, 2026-08-05).
 *
 * The same workbench as Students → Exams, scoped to the **monitored**
 * class-subjects and with the kind pinned to the band test. Deliberately the
 * same screen rather than a band-specific capture surface: a band test IS an
 * exam — `D-76` promotes a locked one to that role — and a second place to
 * record a child's mark would be a second answer to "how did he do".
 *
 * What it does NOT do, and this is `D-70`/`Q-81`:
 *
 *   · **recording a test here does not move anybody's band.** The letter moves
 *     through Manage bands, from a **locked** test (`S-184`), with the moves
 *     reviewed before they commit — because `student_bands` is append-only and
 *     a child slipping B → C is the most consequential thing this module does.
 *     Wiring "save marks" straight to "re-tier the class" would make that
 *     irreversible act a side effect of typing.
 *   · **it ranks nobody.** No completion figure for the owner, no comparison
 *     against another owner, no streak (`S-170`).
 */

import { useQuery } from "@tanstack/react-query";
import { Layers } from "lucide-react";
import Link from "next/link";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ExamWorkbench, type WorkbenchClass } from "@/components/school/exam-workbench";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { PageLoading } from "@/components/ui/page-loading";
import { schoolApi } from "@/lib/school-api";

function BandExamsInner() {
  const { data: scope, isLoading } = useQuery({
    queryKey: ["band-scope"],
    queryFn: () => schoolApi.bandScope(),
  });

  if (isLoading) return <PageLoading label="Loading the programme…" />;
  if (!scope) return null;

  if (!scope.enabled) {
    return (
      <EmptyState icon={Layers} title="No subject is on the support programme yet"
        body="An admin chooses which subjects the school monitors in Setup → Settings → Support programme. Until then there is no band test to record — which is not the same as everybody being fine." />
    );
  }

  const classes: WorkbenchClass[] = scope.classes.map((c) => ({
    class_id: c.class_id,
    class_label: c.class_label,
    subjects: c.subjects,
  }));

  return (
    <div>
      <div className="mb-4">
        <PageHeader title="Band tests"
          subtitle="Record the test a band is read from, for the subjects the school monitors" />
      </div>

      <ExamWorkbench classes={classes} fixedType="band_test"
        captureHint="Only the subjects on the support programme appear here."
        emptyScopeText="None of the subjects you teach are on the support programme, so there is no band test for you to record." />

      <p className="mt-3 text-[11px] leading-snug text-muted-foreground">
        Recording a test here does not move anybody&apos;s band. A letter moves
        from a <span className="font-medium">locked</span> test, in{" "}
        <Link href="/bands/manage" className="text-primary hover:underline">
          Manage bands
        </Link>
        , with the moves shown before they commit — a band is append-only history
        and a child slipping B to C is not something that should happen as a side
        effect of typing marks.
      </p>
    </div>
  );
}

export default function BandExamsPage() {
  return (
    <AuthGuard allow={["admin", "teacher"]}>
      <BandExamsInner />
    </AuthGuard>
  );
}
