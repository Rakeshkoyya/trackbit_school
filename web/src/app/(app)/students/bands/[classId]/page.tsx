"use client";

/**
 * Record a band test (SC-5, admin only) — the same exam capture form pinned to
 * type `band_test`; on save the class is immediately re-categorized into A/B/C
 * by the configured thresholds (append-only band history, P4 intact).
 */

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ExamCapture } from "@/components/school/exam-capture";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";

function BandTestInner() {
  const { classId } = useParams<{ classId: string }>();
  const router = useRouter();
  const { yearId } = useYear();
  const { data: classes = [] } = useQuery({ queryKey: ["classes", yearId], queryFn: () => schoolApi.classes(yearId!), enabled: !!yearId });
  const klass = classes.find((c) => c.id === classId);
  const label = klass ? `${klass.name}${klass.section ? `-${klass.section}` : ""}` : "";

  return (
    <div>
      <div className="mb-4 flex items-center gap-3">
        <Link href="/students/bands" className="rounded-md border border-border bg-card p-2 hover:bg-muted/40">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <PageHeader title={label ? `Band test · Class ${label}` : "Band test"}
          subtitle="Enter the results — saving re-categorizes the class into A/B/C" />
      </div>
      <ExamCapture classId={classId} fixedType="band_test"
        onSaved={async (exam) => {
          try {
            const res = await schoolApi.categorizeBands(exam.id);
            const c = res.counts;
            toast.success(
              `Categorized — A: ${c.A ?? 0} · B: ${c.B ?? 0} · C: ${c.C ?? 0}` +
              (c.no_score ? ` · ${c.no_score} without a score` : "") +
              (res.applied ? ` (${res.applied} moved)` : ""));
          } catch (e) {
            showApiError(e, "Saved, but categorization failed");
          }
          router.push("/students/bands");
        }} />
    </div>
  );
}

export default function BandTestPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <BandTestInner />
    </AuthGuard>
  );
}
