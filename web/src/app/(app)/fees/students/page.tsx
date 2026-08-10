"use client";

/**
 * Fees → Students (FE-1, `D-119`/`D-120`).
 *
 * *"since we already have student data in our system we just show them here, so
 * same selection methods like classes in nav buttons at top and below the table
 * of student will show"*
 *
 * Two things follow from that, and both are departures from the old screen:
 *
 *   · **the roster is the source, not the fee table** (`D-119`). The old page
 *     listed fee *records*, so the forty children nobody had set up were
 *     invisible on the one screen whose job is to notice them. Here every
 *     student in the class appears, and one with no record reads
 *     **"fees not set up"** — a word across the money columns, never ₹0;
 *   · **setting a class up is one action** (`D-120`). Selecting rows bills them
 *     from the class's structure in a single call. Typing a fee per child for a
 *     whole class is what P1v2 calls a mis-designed feature.
 *
 * The class row is the SAME `ClassTabs` the syllabus grid uses — it already
 * sorts in school order (10 after 9) and contains its own overflow. There is no
 * second class picker to keep in step with it.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Search, Users } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { AuthGuard } from "@/components/auth/auth-guard";
import { ClassTabs, sortClasses } from "@/components/school/class-subject-picker";
import { YearSwitcher } from "@/components/school/year-switcher";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import { money } from "@/lib/school-format";
import type { StudentFeeListItem } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const STATUS_TONE: Record<string, "success" | "neutral" | "warning" | "outline"> = {
  paid: "success", partial: "outline", overdue: "warning",
  pending: "neutral", closed: "neutral",
};

const ALL = "__all__";

function StudentsInner() {
  const router = useRouter();
  const qc = useQueryClient();
  const { yearId } = useYear();
  const [classId, setClassId] = useState(ALL);
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<Set<string>>(new Set());

  const { data: rawClasses = [] } = useQuery({
    queryKey: ["classes", yearId, "all"],
    queryFn: () => schoolApi.classes(yearId!),
    enabled: !!yearId,
  });
  const classes = useMemo(() => sortClasses(rawClasses), [rawClasses]);

  // The roster — every student, filtered by class server-side.
  const { data: students = [], isLoading } = useQuery({
    queryKey: ["students", classId],
    queryFn: () => schoolApi.students(classId === ALL ? {} : { class_id: classId }),
    enabled: !!yearId,
  });

  // The fee records that exist. Merged in below; a student with none is not
  // missing data, she is a student nobody has set up yet.
  const { data: fees = [] } = useQuery({
    queryKey: ["student-fees", yearId],
    queryFn: () => schoolApi.studentFees({ year_id: yearId ?? undefined }),
    enabled: !!yearId,
  });
  const feeByStudent = useMemo(() => {
    const map = new Map<string, StudentFeeListItem>();
    for (const row of fees) map.set(row.student_id, row);
    return map;
  }, [fees]);

  const { data: coverage } = useQuery({
    queryKey: ["structure-coverage", yearId],
    queryFn: () => schoolApi.structureCoverage(yearId!),
    enabled: !!yearId,
  });

  const activeClass = classes.find((c) => c.id === classId);
  // Per-class pricing: the structure is found by class NAME, so 6-A and 6-B
  // both resolve to the one row that prices "6".
  const structureRow = activeClass
    ? coverage?.rows.find(
        (r) => r.class_name === activeClass.name && r.structure_id !== null)
    : undefined;

  const rows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return students
      .filter((s) => !needle
        || s.full_name.toLowerCase().includes(needle)
        || (s.admission_no ?? "").toLowerCase().includes(needle))
      .map((s) => ({ student: s, fee: feeByStudent.get(s.id) ?? null }));
  }, [students, feeByStudent, query]);

  const setUpCount = rows.filter((r) => !r.fee).length;

  const apply = useMutation({
    mutationFn: () => schoolApi.applyStructure(structureRow!.structure_id!, {
      student_ids: picked.size ? [...picked] : undefined,
    }),
    onSuccess: (result) => {
      qc.invalidateQueries({ queryKey: ["student-fees"] });
      qc.invalidateQueries({ queryKey: ["structure-coverage"] });
      setPicked(new Set());
      toast.success(result.message);
    },
    onError: (e) => showApiError(e, "Could not set the fees up"),
  });

  const toggle = (id: string) => setPicked((prev) => {
    const next = new Set(prev);
    if (next.has(id)) next.delete(id); else next.add(id);
    return next;
  });

  const selectable = rows.filter((r) => !r.fee).map((r) => r.student.id);
  const allPicked = selectable.length > 0 && selectable.every((id) => picked.has(id));

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <span className="w-14 shrink-0 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
            Class
          </span>
          <button type="button" onClick={() => setClassId(ALL)}
            aria-pressed={classId === ALL}
            className={cn(
              "shrink-0 rounded-full border px-3 py-1.5 text-sm transition-colors",
              classId === ALL
                ? "border-primary bg-primary text-primary-foreground"
                : "border-border bg-card hover:border-primary/60 hover:bg-muted")}>
            All
          </button>
          <ClassTabs classes={classes} classId={classId} onChange={setClassId} />
        </div>
        <YearSwitcher />
      </div>

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="relative min-w-[220px] flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input className="pl-9" placeholder="Search name or admission no…"
            value={query} onChange={(e) => setQuery(e.target.value)} />
        </div>
        {activeClass ? (
          structureRow ? (
            <span className="font-mono text-xs text-muted-foreground">
              {activeClass.name} · {money(structureRow.total_amount ?? "0")} ·{" "}
              {structureRow.num_installments} instalments
            </span>
          ) : (
            // Never a dead end: the tab says what is missing and where to fix it.
            <Button size="sm" variant="outline"
              onClick={() => router.push("/fees/structure")}>
              Class {activeClass.name} is not priced — set the structure
            </Button>
          )
        ) : null}
      </div>

      {isLoading ? (
        <p className="text-sm text-muted-foreground">Loading students…</p>
      ) : rows.length === 0 ? (
        <EmptyState icon={Users} title="No students here"
          body="Pick another class, or clear the search." />
      ) : (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
              <tr>
                <th className="w-9 px-3 py-2.5">
                  {selectable.length > 0 ? (
                    <input type="checkbox" aria-label="Select everyone not set up"
                      checked={allPicked}
                      onChange={() => setPicked(allPicked
                        ? new Set()
                        : new Set(selectable))} />
                  ) : null}
                </th>
                <th className="px-3 py-2.5 text-left font-medium">Student</th>
                <th className="px-3 py-2.5 text-left font-medium">Adm.</th>
                <th className="px-3 py-2.5 text-right font-medium">Net</th>
                <th className="px-3 py-2.5 text-right font-medium">Paid</th>
                <th className="px-3 py-2.5 text-right font-medium">Balance</th>
                <th className="px-3 py-2.5 text-left font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ student, fee }) => (
                <tr key={student.id}
                  onClick={() => router.push(`/fees/students/${student.id}`)}
                  className="cursor-pointer border-t border-border/60 transition-colors hover:bg-muted/40">
                  <td className="px-3 py-2.5" onClick={(e) => e.stopPropagation()}>
                    {!fee ? (
                      <input type="checkbox"
                        aria-label={`Select ${student.full_name}`}
                        checked={picked.has(student.id)}
                        onChange={() => toggle(student.id)} />
                    ) : null}
                  </td>
                  <td className="px-3 py-2.5 font-medium">{student.full_name}</td>
                  <td className="px-3 py-2.5 text-muted-foreground">
                    {student.admission_no ?? "—"}
                  </td>
                  {fee ? (
                    <>
                      <td className="px-3 py-2.5 text-right">{money(fee.net_fee)}</td>
                      <td className="px-3 py-2.5 text-right text-emerald-600 dark:text-emerald-400">
                        {Number(fee.paid) > 0 ? money(fee.paid) : "—"}
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        {Number(fee.pending) > 0 ? money(fee.pending) : "—"}
                      </td>
                      <td className="px-3 py-2.5">
                        <Badge tone={STATUS_TONE[fee.status] ?? "neutral"}>
                          {fee.status}
                        </Badge>
                      </td>
                    </>
                  ) : (
                    // `D-119`: a state, spanning the money columns as one muted
                    // phrase. Four ₹0 cells would say this family owes nothing.
                    <td colSpan={4} className="px-3 py-2.5 text-muted-foreground">
                      fees not set up
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* The action bar. Its confirmation is the number, not a dialog. */}
      {structureRow && (picked.size > 0 || setUpCount > 0) ? (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card px-4 py-3">
          <p className="text-sm text-muted-foreground">
            {picked.size > 0 ? (
              <>
                <span className="font-medium text-foreground">
                  {picked.size} selected
                </span>{" "}
                · {money(String(
                  picked.size * Number(structureRow.total_amount ?? 0)))} will be
                billed
              </>
            ) : (
              <>
                <span className="font-medium text-foreground">
                  {setUpCount} student{setUpCount === 1 ? "" : "s"}
                </span>{" "}
                in view {setUpCount === 1 ? "has" : "have"} no fee record yet
              </>
            )}
          </p>
          <Button size="sm" disabled={apply.isPending}
            onClick={() => apply.mutate()}>
            {apply.isPending
              ? "Setting up…"
              : picked.size > 0
                ? `Set fees for ${picked.size}`
                : `Set fees for class ${activeClass?.name ?? ""}`}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

export default function FeeStudentsPage() {
  return (
    <AuthGuard allow={["admin"]}>
      <StudentsInner />
    </AuthGuard>
  );
}
