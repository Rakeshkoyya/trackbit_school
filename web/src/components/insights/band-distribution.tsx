"use client";

/**
 * The shape of the support programme — school, by class, by subject.
 *
 * Founder call, 2026-08-04. Built once and mounted **twice**: trimmed as the
 * dashboard's band block, in full on ABC Bands → Overview. One component and one
 * server read (`/bands/distribution`), so the summary and the board it links to
 * can never quote different figures for the same morning (`S-51`).
 *
 * Three rules the drawing is built on, all of them load-bearing:
 *
 * **Movement leads.** `S-169` rejected the distribution as the admin's headline
 * and that still holds — a distribution looks identical in a school where nobody
 * has moved for a year. So the sentence at the top is the programme's own
 * movement sentence, and the tiers explain it underneath. What the charts add is
 * the thing movement cannot say: *where* the support load sits.
 *
 * **The unit is the placement, not the child** (`D-75`). There is no overall
 * letter, so a boy who is A in Maths and C in Hindi is in both columns. The
 * caption says so on every mounting, because a reader who assumes "students"
 * will add the school pie up to the roster and find it doesn't.
 *
 * **Not assessed is not a slice.** Nobody having looked at a child is a hole in
 * the record, so it renders as the dashed no-record rail the register (V1-14)
 * and the homework funnel (V1-17) already use — never a fourth colour, never
 * red, never folded into C. A class nobody has banded must not read as a class
 * full of struggling children (ux §5).
 */

import Link from "next/link";

import { BAND_COLOR, ChartCard, Donut } from "@/components/charts";
import { Fraction } from "@/components/insights/shared";
import type { BandDistribution, BandScopeRow } from "@/lib/school-types";
import { cn } from "@/lib/utils";

const TIERS = ["A", "B", "C"] as const;
type Tier = (typeof TIERS)[number];

/** `S-166` in miniature: the letter never travels entirely alone. A one-word
 * gloss is what stops A/B/C reading as a grade on the one screen that shows all
 * three at once. */
const GLOSS: Record<Tier, string> = {
  A: "needs extension",
  B: "keeping up",
  C: "needs support",
};

export function BandLegend({ className = "" }: { className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-1", className)}>
      {TIERS.map((t) => (
        <span key={t} className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="h-2.5 w-2.5 rounded-[3px]" style={{ background: BAND_COLOR[t] }} />
          <span className="font-mono font-medium text-foreground">{t}</span>
          <span>{GLOSS[t]}</span>
        </span>
      ))}
    </div>
  );
}

/**
 * One row's tiers as a 100% stacked bar, with the unassessed remainder shown as
 * a dashed rail rather than a segment.
 *
 * The 2px surface gap between segments is the kit's own mark spec — without it
 * two adjacent violet steps read as one bar with a slight shade change.
 */
function StackBar({ row }: { row: BandScopeRow }) {
  if (!row.assessed) {
    return (
      <div
        className="h-3.5 w-full rounded-[3px] border border-dashed border-border/80"
        title="Nobody has been assessed here yet"
      />
    );
  }
  return (
    <div className="flex h-3.5 w-full gap-[2px] overflow-hidden rounded-[3px]">
      {TIERS.map((t) => {
        const pct = row[`${t.toLowerCase()}_pct` as "a_pct" | "b_pct" | "c_pct"];
        if (!pct) return null;
        const n = row[t.toLowerCase() as "a" | "b" | "c"];
        return (
          <div
            key={t}
            style={{ width: `${pct}%`, background: BAND_COLOR[t] }}
            title={`${t} — ${n} of ${row.assessed} (${pct}%)`}
          />
        );
      })}
    </div>
  );
}

function ScopeList({
  rows, unit, emptyLabel,
}: {
  rows: BandScopeRow[];
  unit: string;
  emptyLabel: string;
}) {
  if (!rows.length) {
    return <p className="py-6 text-center text-xs text-muted-foreground">{emptyLabel}</p>;
  }
  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r.key} className="space-y-1">
          <div className="flex items-baseline justify-between gap-3">
            <span className="truncate text-[13px] font-medium">{r.label}</span>
            {/* The denominator rides on every row — `assessed`, never the
                roster, because that is what the bar is a percentage of. */}
            <span className="shrink-0 text-[11px] text-muted-foreground">
              {r.assessed ? (
                <>
                  <Fraction n={r.c} of={r.assessed} className="text-[11px]" />
                  <span className="ml-1">in C</span>
                </>
              ) : (
                "not assessed"
              )}
            </span>
          </div>
          <StackBar row={r} />
          {r.not_assessed ? (
            <p className="text-[10.5px] text-muted-foreground">
              {r.not_assessed} {unit} not assessed yet
            </p>
          ) : null}
        </div>
      ))}
    </div>
  );
}

/** The school pie — the one place a single figure is the whole story. */
export function BandSchoolDonut({ data, size = 168 }: { data: BandDistribution; size?: number }) {
  const slices = TIERS.map((t) => ({
    label: t,
    value: data.school[t.toLowerCase() as "a" | "b" | "c"],
    color: BAND_COLOR[t],
  })).filter((s) => s.value > 0);

  if (!slices.length) {
    return (
      <div
        className="flex items-center justify-center rounded-full border border-dashed border-border text-center text-[11px] text-muted-foreground"
        style={{ width: size, height: size }}
      >
        Nobody assessed
        <br />
        yet
      </div>
    );
  }
  return (
    <Donut
      slices={slices}
      size={size}
      centerValue={`${data.school.c_pct}%`}
      centerLabel="in Band C"
    />
  );
}

export function BandDistributionView({
  data, compact = false, href = "/bands",
}: {
  data: BandDistribution;
  /** The dashboard mounting: the sentence, the pie and the two worst rows. */
  compact?: boolean;
  href?: string;
}) {
  const classRows = compact ? data.by_class.slice(0, 3) : data.by_class;
  const subjectRows = compact ? data.by_subject.slice(0, 3) : data.by_subject;

  if (!data.subjects.length) {
    return (
      <div className="rounded-xl border border-dashed border-border p-5 text-sm text-muted-foreground">
        {data.caption || "No subject is being monitored yet."}{" "}
        <Link href="/setup/settings" className="underline underline-offset-2">
          Choose the subjects to monitor
        </Link>
        .
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* `S-169`: movement is the headline; the distribution explains it. */}
      <div>
        <p className="text-sm leading-relaxed">{data.headline}</p>
        <p className="mt-1 text-[11px] text-muted-foreground">{data.caption}</p>
      </div>

      <div className={cn("grid gap-4", compact ? "sm:grid-cols-2" : "lg:grid-cols-3")}>
        <ChartCard
          title="Across the school"
          hint="One child counts once per monitored subject — there is no overall band."
        >
          <div className="flex flex-col items-center gap-3">
            <BandSchoolDonut data={data} size={compact ? 148 : 168} />
            <BandLegend className="justify-center" />
            {data.school.not_assessed ? (
              <p className="text-center text-[11px] text-muted-foreground">
                {data.school.not_assessed} placement
                {data.school.not_assessed === 1 ? "" : "s"} not assessed yet — a gap in
                the record, not a result
              </p>
            ) : null}
          </div>
        </ChartCard>

        <ChartCard title="By class" hint="Share of each class's assessed placements. Worst first.">
          <ScopeList
            rows={classRows}
            unit="placements"
            emptyLabel="No class has been assessed yet."
          />
          {compact && data.by_class.length > classRows.length ? (
            <p className="mt-3 text-[11px] text-muted-foreground">
              +{data.by_class.length - classRows.length} more classes
            </p>
          ) : null}
        </ChartCard>

        <ChartCard
          title="By subject"
          hint="Only the subjects chosen in Setup → Settings. Here the unit is children."
        >
          <ScopeList
            rows={subjectRows}
            unit="children"
            emptyLabel="No subject has been assessed yet."
          />
          {compact && data.by_subject.length > subjectRows.length ? (
            <p className="mt-3 text-[11px] text-muted-foreground">
              +{data.by_subject.length - subjectRows.length} more subjects
            </p>
          ) : null}
        </ChartCard>
      </div>

      {compact ? (
        <Link href={href} className="inline-block text-xs font-medium underline underline-offset-2">
          Open ABC bands
        </Link>
      ) : null}
    </div>
  );
}
