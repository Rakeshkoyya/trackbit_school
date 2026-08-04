"use client";

/**
 * ABC bands → Reports.
 *
 * How each class and subject is *growing* — which is movement, not standing.
 * The distribution answers "where is the load"; this tab answers "is the
 * programme working", and they are different questions with different shapes.
 *
 * The grid is `ProgrammeGridCell`, which has carried `moved_up`/`slipped` per
 * class-subject since V1-9 and was rendered as two bare numbers in a table
 * nobody could scan. Here each cell reads as a movement, worst first, with the
 * C-count as the load it happened against.
 *
 * **No ranking of teachers** (`S-170`) — this page groups by class and subject
 * and never by owner. The children handed to the best teacher are by
 * construction the hardest ones, so a league table of movement measures
 * allocation, not teaching.
 *
 * A child's own report — his week, his tests, the AI summary — is his student
 * page and his support page. Nothing about one child is re-rendered here.
 */

import { useQuery } from "@tanstack/react-query";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import Link from "next/link";

import { BandLegend } from "@/components/insights/band-distribution";
import { ColumnHead, Empty, Fraction, Section } from "@/components/insights/shared";
import { YearSwitcher } from "@/components/school/year-switcher";
import { PageHeader } from "@/components/ui/page-header";
import { useYear } from "@/contexts/year-context";
import { schoolApi } from "@/lib/school-api";
import { cn } from "@/lib/utils";

function Move({ up, down }: { up: number; down: number }) {
  const net = up - down;
  const Icon = net > 0 ? ArrowUpRight : net < 0 ? ArrowDownRight : Minus;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 font-mono text-[12px] tabular-nums",
        net > 0 && "text-[color:var(--success,#234a37)]",
        net < 0 && "text-[color:var(--danger,#d8624e)]",
        net === 0 && "text-muted-foreground",
      )}
    >
      <Icon className="h-3.5 w-3.5" />
      {up}↑ {down}↓
    </span>
  );
}

export default function BandReportsPage() {
  const { yearId } = useYear();
  const { data: scope } = useQuery({ queryKey: ["band-scope"], queryFn: schoolApi.bandScope });
  const isAdmin = scope?.is_admin ?? false;

  const { data, isLoading } = useQuery({
    queryKey: ["band-programme", yearId],
    queryFn: () => schoolApi.bandProgramme(),
    enabled: isAdmin,
  });
  const { data: dist } = useQuery({
    queryKey: ["band-distribution", yearId],
    queryFn: () => schoolApi.bandDistribution(),
  });

  if (!isAdmin) {
    return (
      <div className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">
        The programme report is the admin&apos;s view of the whole school. Your own
        children are under <Link href="/bands/my-students" className="underline">My students</Link>,
        and each child&apos;s full report opens from there.
      </div>
    );
  }

  // Worst first: most slipped, then fewest moved up. The list exists to find
  // where the programme is not working.
  const grid = [...(data?.grid ?? [])].sort(
    (a, b) => b.slipped - a.slipped || a.moved_up - b.moved_up || a.c_count - b.c_count,
  );

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader
          title="Programme report"
          subtitle="Movement by class and subject — is the support actually moving children?"
        />
        <YearSwitcher />
      </div>

      {isLoading || !data ? (
        <div className="h-64 animate-pulse rounded-xl bg-muted" />
      ) : (
        <>
          <div className="rounded-xl border border-border bg-card p-4">
            <p className="text-sm leading-relaxed">{data.headline}</p>
            {dist ? <p className="mt-1 text-[11px] text-muted-foreground">{dist.caption}</p> : null}
          </div>

          <Section
            title="By class and subject"
            hint="Movement this term, against the number of Band C children it happened to."
          >
            {grid.length ? (
              <div className="overflow-hidden rounded-xl border border-border bg-card">
                <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto] gap-3 px-3 py-2">
                  <ColumnHead>Class</ColumnHead>
                  <ColumnHead>Subject</ColumnHead>
                  <ColumnHead>In C</ColumnHead>
                  <ColumnHead>Moved</ColumnHead>
                </div>
                {grid.map((c) => (
                  <div
                    key={`${c.class_id}-${c.subject_id}`}
                    className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto] items-center gap-3 border-t border-border px-3 py-2.5"
                  >
                    <span className="truncate text-sm font-medium">{c.class_label}</span>
                    <span className="truncate text-sm text-muted-foreground">{c.subject_name}</span>
                    <span className="font-mono text-[12px] tabular-nums">{c.c_count}</span>
                    <Move up={c.moved_up} down={c.slipped} />
                  </div>
                ))}
              </div>
            ) : (
              <Empty>Nothing has been banded this term yet.</Empty>
            )}
          </Section>

          {dist ? (
            <Section
              title="Standing, by subject"
              hint="Where the children are now — the counterpart to the movement above."
            >
              <div className="space-y-2 rounded-xl border border-border bg-card p-4">
                <BandLegend />
                <div className="mt-2 space-y-2">
                  {dist.by_subject.map((s) => (
                    <div key={s.key} className="flex items-center justify-between gap-3 text-sm">
                      <span className="truncate">{s.label}</span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        A {s.a} · B {s.b} · C {s.c} ·{" "}
                        <Fraction n={s.assessed} of={s.eligible} className="text-[11px]" /> assessed
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </Section>
          ) : null}

          <Section title="Still in Band C" hint="Each child's own report opens from his name.">
            {data.stuck.length ? (
              <div className="space-y-2">
                {data.stuck.map((r) => (
                  <Link
                    key={`${r.student_id}-${r.subject_id}`}
                    href={
                      r.intervention_id ? `/support/${r.intervention_id}` : `/students/${r.student_id}`
                    }
                    className="flex items-center gap-3 rounded-lg border border-border bg-card px-4 py-3 transition-colors hover:bg-muted/40"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-medium">{r.full_name}</span>
                      <span className="block text-xs text-muted-foreground">
                        {r.class_label} · {r.subject_name}
                        {r.owner_name ? ` · owner ${r.owner_name}` : " · no owner yet"}
                        {r.last_checkin ? ` · last check-in ${r.last_checkin}` : ""}
                      </span>
                    </span>
                  </Link>
                ))}
              </div>
            ) : (
              <Empty>Nobody is stuck in Band C.</Empty>
            )}
          </Section>
        </>
      )}
    </div>
  );
}
