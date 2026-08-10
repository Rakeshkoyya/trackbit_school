"use client";

/**
 * Fees → Dashboard (FE-1).
 *
 * The V1-10 collection board, unchanged — quarter strip, pace marker, class
 * table with both denominators, named defaulters. It is the one computation
 * every fee screen renders (`S-152`), and nothing here re-derives any part of it.
 *
 * What FE-1 adds is the **empty state**. A school that has not priced anything
 * yet used to land on a board of zeroes, which reads as "you have collected
 * nothing" rather than "you have not started". Zero and not-yet are different
 * facts, and only one of them is anybody's fault.
 *
 * The student list that used to live under this board has moved to its own tab,
 * where it belongs and where it can show the children nobody has set up.
 */

import { useQuery } from "@tanstack/react-query";
import { IndianRupee } from "lucide-react";
import { useRouter } from "next/navigation";

import { AuthGuard } from "@/components/auth/auth-guard";
import { CollectionBoard } from "@/components/school/collection-board";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";

function DashboardInner() {
  const router = useRouter();
  const { yearId } = useYear();

  const { data: coverage, isLoading } = useQuery({
    queryKey: ["structure-coverage", yearId],
    queryFn: () => schoolApi.structureCoverage(yearId!),
    enabled: !!yearId,
  });

  const nothingPriced = !!coverage && coverage.classes_priced === 0;

  return (
    <div>
      <div className="mb-4 flex justify-end">
        <YearSwitcher />
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : nothingPriced ? (
        <EmptyState
          icon={IndianRupee}
          title="No fees priced for this year yet"
          body="The fee structure is the year's backbone — a total and an instalment schedule per class. Start there, then set your students up in one action."
          action={
            <Button size="sm" onClick={() => router.push("/fees/structure")}>
              Set the fee structure
            </Button>
          }
        />
      ) : (
        <CollectionBoard yearId={yearId} />
      )}
    </div>
  );
}

export default function FeesDashboardPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <DashboardInner />
    </AuthGuard>
  );
}
