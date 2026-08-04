"use client";

/**
 * ABC bands → Teacher allocation (admin only).
 *
 * Every Band C placement in the school and the teacher who owns moving it to B,
 * groupable and filterable by class and subject. Before this, an owner could
 * only be assigned one child at a time off the programme board, which is why
 * `D-71` shipped as *"already implemented as a dead link"* — the screen where
 * you would do a term's allocation in one sitting did not exist.
 *
 * Three rules on this page:
 *
 * **Unassigned first, always.** The screen exists for the empty column; sorting
 * alphabetically would bury it.
 *
 * **Every row names its subject** (`S-188`). One owner *per subject* (`D-77`)
 * means a child who is C in two subjects has two owners, and "Kabir Shah —
 * owner Priya" lets each of them assume the other is on it.
 *
 * **Suggested, never restricted.** The picker puts the teachers already in
 * front of this child at the top *with the reason*, and still lists everyone: a
 * school whose subject teacher is on leave has to be able to assign somebody,
 * and a picker that refuses is one the office routes around by phone. Each
 * option carries the teacher's current load as **capacity, never a score** —
 * `S-170` is a fence, and the children handed to the best teacher are by
 * construction the hardest ones.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { ColumnHead, Empty, ScrollX } from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Sheet } from "@/components/ui/sheet";
import { useYear } from "@/contexts/year-context";
import { showApiError } from "@/lib/errors";
import { schoolApi } from "@/lib/school-api";
import type { AllocationRow } from "@/lib/school-types";
import { cn } from "@/lib/utils";

type GroupBy = "none" | "class" | "subject";

function AssignSheet({ row, onClose }: { row: AllocationRow | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [member, setMember] = useState("");
  const [criterion, setCriterion] = useState("");

  const { data: suggestions = [] } = useQuery({
    queryKey: ["band-owner-suggestions", row?.student_id, row?.subject_id],
    queryFn: () => schoolApi.bandOwnerSuggestions(row!.student_id, row!.subject_id),
    enabled: !!row,
  });
  const suggested = suggestions.filter((s) => s.suggested);
  const others = suggestions.filter((s) => !s.suggested);

  const save = useMutation({
    mutationFn: () =>
      schoolApi.assignBandOwner({
        student_id: row!.student_id,
        subject_id: row!.subject_id,
        member_id: member || null,
        exit_criterion: criterion.trim() || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["band-allocation"] });
      qc.invalidateQueries({ queryKey: ["band-programme"] });
      toast.success("Owner assigned — the child is on their list today");
      setMember("");
      setCriterion("");
      onClose();
    },
    onError: (e) => showApiError(e, "Could not assign"),
  });

  const Option = ({ s }: { s: (typeof suggestions)[number] }) => (
    <button
      type="button"
      onClick={() => setMember(s.member_id)}
      className={cn(
        "flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2 text-left transition-colors",
        member === s.member_id
          ? "border-primary bg-primary/5"
          : "border-border hover:bg-muted/40",
      )}
    >
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium">
          {s.name}
          {s.current ? <span className="ml-2 text-xs text-muted-foreground">current owner</span> : null}
        </span>
        {s.reason ? (
          <span className="block truncate text-xs text-muted-foreground">{s.reason}</span>
        ) : null}
      </span>
      {/* Capacity, not performance — how many children they already carry. */}
      <span className="shrink-0 font-mono text-[11px] text-muted-foreground">
        {s.load ? `${s.load} already` : "none yet"}
      </span>
    </button>
  );

  return (
    <Sheet
      open={!!row}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
      title={row ? `${row.full_name} · ${row.subject_name}` : ""}
    >
      {row ? (
        <div className="space-y-4">
          <p className="text-xs text-muted-foreground">
            One owner per subject. A child who is C in two subjects has two owners, and
            each knows exactly what hers is.
          </p>

          {suggested.length ? (
            <div className="space-y-2">
              <ColumnHead>Suggested</ColumnHead>
              {suggested.map((s) => (
                <Option key={s.member_id} s={s} />
              ))}
            </div>
          ) : null}

          {others.length ? (
            <div className="space-y-2">
              <ColumnHead>Anyone else</ColumnHead>
              <div className="max-h-56 space-y-2 overflow-y-auto">
                {others.map((s) => (
                  <Option key={s.member_id} s={s} />
                ))}
              </div>
            </div>
          ) : null}

          <div>
            <Label htmlFor="crit">Moves to B when… (optional)</Label>
            <textarea
              id="crit"
              rows={2}
              value={criterion}
              onChange={(e) => setCriterion(e.target.value)}
              placeholder="reads a grade-level passage at 60 wpm with ≤3 errors, twice running"
              className="mt-1 w-full rounded-md border border-border bg-card px-2 py-2 text-sm"
            />
            <p className="mt-1 text-xs text-muted-foreground">
              Written now, not judged at the end of term — otherwise the owner is scored
              on a judgement she also makes.
            </p>
          </div>

          <Button className="w-full" disabled={save.isPending} onClick={() => save.mutate()}>
            {member ? "Assign" : "Assign the subject teacher (default)"}
          </Button>
        </div>
      ) : null}
    </Sheet>
  );
}

function Row({ row, onAssign }: { row: AllocationRow; onAssign: () => void }) {
  return (
    <div className="grid grid-cols-[1fr_auto] items-center gap-3 border-t border-border px-3 py-2.5 sm:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1.4fr)_auto]">
      <div className="min-w-0">
        <Link href={`/students/${row.student_id}`} className="text-sm font-medium hover:underline">
          {row.full_name}
        </Link>
        <p className="text-xs text-muted-foreground sm:hidden">
          {row.class_label} · {row.subject_name}
        </p>
      </div>
      <p className="hidden truncate text-xs text-muted-foreground sm:block">
        {row.class_label} · {row.subject_name}
      </p>
      <div className="hidden min-w-0 sm:block">
        {row.owner_name ? (
          <>
            <p className="truncate text-sm">{row.owner_name}</p>
            <p className="text-xs text-muted-foreground">
              {row.checkins
                ? `${row.checkins} check-in${row.checkins === 1 ? "" : "s"}${
                    row.last_checkin ? ` · last ${row.last_checkin}` : ""
                  }`
                : "never checked in"}
            </p>
          </>
        ) : (
          <span className="text-xs text-muted-foreground">nobody assigned</span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {row.owner_name ? null : <Badge tone="warning">open</Badge>}
        <Button size="sm" variant={row.owner_name ? "outline" : "primary"} onClick={onAssign}>
          <UserPlus className="h-4 w-4" />
          {row.owner_name ? "Reassign" : "Assign"}
        </Button>
      </div>
    </div>
  );
}

export default function AllocationPage() {
  const { yearId } = useYear();
  const [classId, setClassId] = useState("");
  const [subjectId, setSubjectId] = useState("");
  const [groupBy, setGroupBy] = useState<GroupBy>("class");
  const [assignFor, setAssignFor] = useState<AllocationRow | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["band-allocation", yearId, classId, subjectId],
    queryFn: () =>
      schoolApi.bandAllocation({
        classId: classId || undefined,
        subjectId: subjectId || undefined,
      }),
  });

  const groups = (() => {
    const rows = data?.rows ?? [];
    if (groupBy === "none") return [{ label: "", rows }];
    const key = (r: AllocationRow) =>
      groupBy === "class" ? (r.class_label ?? "No class") : r.subject_name;
    const map = new Map<string, AllocationRow[]>();
    for (const r of rows) {
      const k = key(r);
      if (!map.has(k)) map.set(k, []);
      map.get(k)!.push(r);
    }
    return [...map.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([label, rows_]) => ({ label, rows: rows_ }));
  })();

  return (
    <div className="space-y-4">
      <PageHeader
        title="Teacher allocation"
        subtitle="Every Band C child and the teacher who owns moving them to B."
      />

      {isLoading || !data ? (
        <div className="h-64 animate-pulse rounded-xl bg-muted" />
      ) : (
        <>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm leading-relaxed">{data.headline}</p>
            <div className="mt-2 flex items-center gap-3 text-xs">
              <Badge tone={data.unassigned ? "warning" : "success"}>
                {data.unassigned} without an owner
              </Badge>
              <Badge tone="neutral">{data.assigned} assigned</Badge>
            </div>
          </div>

          {/* Filters in one row above what they scope (dataviz §interaction). */}
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="rounded-md border border-border bg-card px-2 py-1.5 text-sm"
              value={classId}
              onChange={(e) => setClassId(e.target.value)}
            >
              <option value="">All classes</option>
              {data.classes.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
            <select
              className="rounded-md border border-border bg-card px-2 py-1.5 text-sm"
              value={subjectId}
              onChange={(e) => setSubjectId(e.target.value)}
            >
              <option value="">All subjects</option>
              {data.subjects.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.label}
                </option>
              ))}
            </select>
            <select
              className="rounded-md border border-border bg-card px-2 py-1.5 text-sm"
              value={groupBy}
              onChange={(e) => setGroupBy(e.target.value as GroupBy)}
            >
              <option value="class">Group by class</option>
              <option value="subject">Group by subject</option>
              <option value="none">No grouping</option>
            </select>
          </div>

          {data.rows.length ? (
            <div className="space-y-4">
              {groups.map((g) => (
                <div key={g.label} className="overflow-hidden rounded-xl border border-border bg-card">
                  {g.label ? (
                    <div className="flex items-center justify-between px-3 py-2">
                      <ColumnHead count={g.rows.length}>{g.label}</ColumnHead>
                      <span className="font-mono text-[10px] text-muted-foreground">
                        {g.rows.filter((r) => !r.owner_member_id).length} open
                      </span>
                    </div>
                  ) : null}
                  <ScrollX>
                    <div className="min-w-[520px]">
                      {g.rows.map((r) => (
                        <Row
                          key={`${r.student_id}-${r.subject_id}`}
                          row={r}
                          onAssign={() => setAssignFor(r)}
                        />
                      ))}
                    </div>
                  </ScrollX>
                </div>
              ))}
            </div>
          ) : (
            <Empty>No child is in Band C for this filter.</Empty>
          )}
        </>
      )}

      <AssignSheet row={assignFor} onClose={() => setAssignFor(null)} />
    </div>
  );
}
