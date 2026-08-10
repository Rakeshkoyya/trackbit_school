"use client";

/**
 * Fees → Structure (FE-1, `D-117`).
 *
 * *"the first step is to enter the fee structure this is the backbone of that
 * year data … once all the classes and fee structure is done"* — that last
 * clause is a **completeness check**, and it is why this is a coverage grid
 * rather than the list of structures the old screen showed.
 *
 * A list can only draw the rows that exist. The row that matters here is the
 * class nobody has priced yet, so every class in the year gets a line whether it
 * has a structure or not, and the unpriced ones read **"not priced"** — a word,
 * never ₹0, which would say the class is free.
 */

import { useQuery } from "@tanstack/react-query";
import { IndianRupee, Plus } from "lucide-react";
import { useMemo, useState } from "react";

import { AuthGuard } from "@/components/auth/auth-guard";
import { FeeStructureEditor } from "@/components/school/fee-structure-editor";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";
import { money } from "@/lib/school-format";
import type { ClassCoverageRow } from "@/lib/school-types";

function StructureInner() {
  const { yearId } = useYear();
  const [editing, setEditing] = useState<ClassCoverageRow | null>(null);
  const [open, setOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["structure-coverage", yearId],
    queryFn: () => schoolApi.structureCoverage(yearId!),
    enabled: !!yearId,
  });

  const classNames = useMemo(
    () => Array.from(new Set((data?.rows ?? []).map((r) => r.class_name))),
    [data],
  );

  const openRow = (row: ClassCoverageRow) => {
    setEditing(row);
    setOpen(true);
  };

  const priced = data?.classes_priced ?? 0;
  const totalClasses = data?.classes_total ?? 0;

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <p className="text-sm text-muted-foreground">
          The year&rsquo;s backbone. Every student&rsquo;s fee starts here.
        </p>
        <div className="flex items-center gap-2">
          {/* The completeness figure the founder asked for, carrying its
              denominator like every other figure in this codebase. */}
          {totalClasses > 0 ? (
            <span className="font-mono text-xs text-muted-foreground">
              {priced} of {totalClasses} classes priced
            </span>
          ) : null}
          <YearSwitcher />
        </div>
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading classes…</p>
      ) : !data || data.rows.length === 0 ? (
        <EmptyState
          icon={IndianRupee}
          title="No classes in this year yet"
          body="Fee structures are priced per class, so add the year's classes first — then come back and give each one a total and a schedule."
        />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="px-4 py-2.5 text-left font-medium">Class</th>
                <th className="px-4 py-2.5 text-left font-medium">Sections</th>
                <th className="px-4 py-2.5 text-left font-medium">Category</th>
                <th className="px-4 py-2.5 text-right font-medium">Total</th>
                <th className="px-4 py-2.5 text-left font-medium">Schedule</th>
                <th className="px-4 py-2.5 text-right font-medium">Students</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, idx) => {
                const unpriced = row.structure_id === null;
                return (
                  <tr
                    key={`${row.class_name}-${row.category_id ?? "all"}-${idx}`}
                    onClick={() => openRow(row)}
                    className="cursor-pointer border-t border-border/60 transition-colors hover:bg-muted/40"
                  >
                    <td className="px-4 py-2.5 font-medium">{row.class_name}</td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {row.sections.length ? row.sections.join(" · ") : "—"}
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {row.category_name ?? (unpriced ? "—" : "All")}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      {unpriced ? (
                        // A state, in words. ₹0 would read as "this class is free".
                        <span className="text-amber-600 dark:text-amber-400">
                          not priced
                        </span>
                      ) : (
                        <span className="font-semibold">
                          {money(row.total_amount ?? "0")}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-muted-foreground">
                      {unpriced ? "—" : `${row.num_installments} instalments`}
                    </td>
                    <td className="px-4 py-2.5 text-right text-muted-foreground">
                      {unpriced ? (
                        row.students_total > 0
                          ? <span>{row.students_total} waiting</span>
                          : "—"
                      ) : (
                        // Both denominators: how many are ON this price, out of
                        // how many are in the class. `D-118` needs the first
                        // number visible before anybody edits.
                        <span>{row.students_on} of {row.students_total}</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {classNames.length > 0 ? (
        <div className="mt-4">
          <Button size="sm" variant="outline"
            onClick={() => { setEditing(null); setOpen(true); }}>
            <Plus className="h-4 w-4" /> Price a class
          </Button>
          <p className="mt-2 text-xs text-muted-foreground">
            A structure prices the whole class — one entry for 6 covers every
            section of it. Use a category for a different price within the same
            class, like a staff ward.
          </p>
        </div>
      ) : null}

      {open ? (
        <FeeStructureEditor
          // Remounts per row, so the form always opens on that row's numbers
          // rather than whatever the last one left in state.
          key={editing?.structure_id ?? editing?.class_name ?? "new"}
          open={open}
          onOpenChange={setOpen}
          row={editing}
          yearId={yearId}
          classNames={classNames}
        />
      ) : null}
    </div>
  );
}

export default function FeeStructurePage() {
  return (
    <AuthGuard allow={["admin"]}>
      <StructureInner />
    </AuthGuard>
  );
}
