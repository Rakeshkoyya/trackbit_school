"use client";

/**
 * `/fees/{student_fee_id}` → `/fees/students/{student_id}` (FE-1, `D-125`).
 *
 * The family page is routed by **student** now, so that a child nobody has set
 * up yet still has a page to be set up on. This path is kept alive because the
 * collection board's defaulter rows carry `student_fee_id` and have linked here
 * since V1-10 — changing the route without this would have turned every
 * defaulter link on the dashboard into a dead end.
 *
 * Next matches static segments before dynamic ones, so `/fees/students` and
 * `/fees/structure` reach their own pages and only a real id lands here.
 */

import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { use, useEffect } from "react";

import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

function Redirector({ feeId }: { feeId: string }) {
  const router = useRouter();
  const { yearId } = useYear();

  const { data: fees, isLoading } = useQuery({
    queryKey: ["student-fees", yearId],
    queryFn: () => schoolApi.studentFees({ year_id: yearId ?? undefined }),
    enabled: !!yearId,
  });

  const studentId = fees?.find((f) => f.id === feeId)?.student_id;

  useEffect(() => {
    if (studentId) {
      router.replace(`/fees/students/${studentId}`);
    } else if (fees && !isLoading) {
      // A record from another year is not in this year's list. Send her to the
      // table rather than leaving her on a spinner that never resolves.
      router.replace("/fees/students");
    }
  }, [studentId, fees, isLoading, router]);

  return <p className="text-sm text-muted-foreground">Opening the record…</p>;
}

export default function LegacyFeeDetailPage({ params }: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  return <Redirector feeId={id} />;
}
