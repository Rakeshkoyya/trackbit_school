"use client";

// Fees, drawn against the calendar that governs them.
//
// A collection percentage cannot be read on its own. 45% is excellent in May
// and alarming in February, and the old board printed it bare — four figures on
// one line, then a strip of quarter buttons carrying a percentage each. The
// admin had to know the fee calendar by heart to know whether any of it was
// good news.
//
// So every figure here sits on a track carrying the schedule's own marker: the
// arc is what came in, the tick is what the school had ASKED for by today, and
// the distance between them is the finding. Arc past the tick means families
// paid early; arc short of it means money the school expected and does not
// have, and that gap is a number worth ringing someone about.
//
// It is deliberately the same device V1-15 put on the syllabus board, at the
// same three scales — a big ring for the whole, small rings for the parts, a
// bar for a row — so an admin who has learned to read one board can read this
// one. The tick means the same thing on both: *where you should be by now*.
//
// Three rules this must not break:
//
//   * **A quarter that has not come due is neutral and says so.** It has not
//     been missed. Painting next January red every August is how a board stops
//     being read (ux §5, §10). `tone` and `state` are decided server-side so
//     this cannot be re-litigated per component.
//   * **collected · pending · overdue are never added.** `Collection` has no
//     `outstanding` property on purpose (`S-163`); pending is a forecast and
//     overdue is a phone call. The old dashboard block added them in the
//     browser and called the result "outstanding".
//   * **Dues carried from a previous year are their own line** (`D-88`), never
//     inside these figures.

import type { ReactNode } from "react";

import { PaceRing } from "@/components/charts";
import { ColumnHead, Fraction } from "@/components/insights/shared";
import type { QuarterRow, YearCollection } from "@/lib/school-types";

/** Full rupees with Indian grouping — for ledgers, where the exact figure is
 *  the point and the eye has time. */
export const money = (n: number) =>
  `₹${Math.round(n).toLocaleString("en-IN")}`;

/** Lakh/crore short form — for a ring centre, where "₹1,35,000" at 26px either
 *  overflows the hole or shrinks the type below reading size. Indian units, not
 *  K/M: a school reads ₹1.4L instantly and ₹135K not at all. */
export function shortMoney(n: number): string {
  const a = Math.abs(n);
  if (a >= 1e7) return `₹${(n / 1e7).toFixed(a >= 1e8 ? 0 : 1)}Cr`;
  if (a >= 1e5) return `₹${(n / 1e5).toFixed(a >= 1e6 ? 0 : 1)}L`;
  if (a >= 1000) return `₹${Math.round(n / 1000)}k`;
  return `₹${Math.round(n)}`;
}

const TONE_TEXT: Record<string, string> = {
  green: "text-success", amber: "text-warning", red: "text-danger",
  neutral: "text-muted-foreground",
};

/** One ruled line of the ledger beside the ring. The register voice: mono for
 *  anything countable, sans for anything readable. */
function LedgerLine({ label, value, note, strong = false, tone }: {
  label: string; value: string; note?: ReactNode; strong?: boolean; tone?: string;
}) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-t border-border/70 py-1.5 first:border-t-0">
      <div className="min-w-0">
        <ColumnHead>{label}</ColumnHead>
        {note ? <p className="mt-0.5 text-[11px] leading-snug text-muted-foreground">{note}</p> : null}
      </div>
      <span className={`shrink-0 font-mono tabular-nums ${strong ? "text-[15px] font-semibold" : "text-[13px]"} ${
        tone ? TONE_TEXT[tone] ?? "" : ""}`}>
        {value}
      </span>
    </div>
  );
}

/** SECTION 1 — the whole year: one arc, one marker, three figures.
 *
 *  `compact` is the dashboard's copy of the same device, off the same payload,
 *  so the block and the fees page cannot quote different numbers. */
export function YearFeeRing({ year, compact = false }: {
  year: YearCollection; compact?: boolean;
}) {
  const nothingBilled = year.billed <= 0;
  const nothingDue = !nothingBilled && year.due_by_today <= 0;
  const ahead = year.collected > year.due_by_today && year.due_by_today > 0;
  const size = compact ? 132 : 168;

  return (
    // Stacked below `sm`: side by side at 360px left the ledger about 150px
    // wide, which wrapped "everything asked for this year" one word per line
    // and let the amounts collide with their own labels.
    <div className={`flex flex-col items-center gap-4 sm:flex-row sm:items-center ${
      compact ? "" : "sm:gap-6"}`}>
      <div className="shrink-0">
        <PaceRing
          pct={nothingBilled ? null : Math.min(100, year.pct ?? 0)}
          expectedPct={nothingBilled || nothingDue ? null : year.due_pct}
          tone={year.tone} size={size} stroke={compact ? 11 : 13}>
          <span className={`font-mono font-semibold leading-none tabular-nums ${
            compact ? "text-[19px]" : "text-[24px]"}`}>
            {nothingBilled ? "—" : shortMoney(year.collected)}
          </span>
          <span className="mt-1 font-mono text-[9px] uppercase tracking-[0.1em] text-muted-foreground">
            collected
          </span>
        </PaceRing>
      </div>

      <div className="w-full min-w-0 flex-1">
        <LedgerLine label="Total billed" value={money(year.billed)}
          note={compact ? undefined : "everything asked for this year"} />
        <LedgerLine label="Due by today" value={money(year.due_by_today)}
          note={compact ? undefined : "the instalments whose date has arrived"} />
        <LedgerLine label="Collected" value={money(year.collected)} strong
          note={compact ? undefined : (year.pct != null ? `${year.pct}% of what was billed` : undefined)} />
        {nothingBilled ? (
          <p className="pt-2 text-[11px] text-muted-foreground">
            Nothing has been billed for this year yet.
          </p>
        ) : nothingDue ? (
          <p className="pt-2 text-[11px] text-muted-foreground">
            No instalment has come due yet — nothing is late.
          </p>
        ) : ahead ? (
          <LedgerLine label="Ahead by" tone="green"
            value={money(year.collected - year.due_by_today)}
            note={compact ? undefined : "families who paid before the date"} />
        ) : (
          <LedgerLine label="Short by" tone={year.tone}
            value={money(year.shortfall)}
            note={compact ? undefined : "asked for by today and not in"} />
        )}
      </div>
    </div>
  );
}

/** SECTION 2 — one ring per quarter, each on its own denominator.
 *
 *  These ARE independent scopes, so separate rings is the honest form here
 *  (unlike the year's three figures, which share one). A quarter nobody has
 *  been asked to pay yet gets a dashed track and a word, never a red zero. */
export function QuarterRings({ quarters, onPick, picked }: {
  quarters: QuarterRow[];
  onPick?: (label: string) => void;
  picked?: string | null;
}) {
  if (!quarters.length) return null;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {quarters.map((q) => {
        const nothingBilled = q.billed <= 0;
        const nothingDue = !nothingBilled && q.due_by_today <= 0;
        const caption = nothingBilled ? "nothing billed"
          : nothingDue ? "not due yet"
            : q.shortfall > 0 ? `${shortMoney(q.shortfall)} short`
              : q.collected > q.due_by_today ? "paid ahead" : "on schedule";
        const inner = (
          <>
            <div className="mb-1 flex items-baseline justify-between gap-2">
              <ColumnHead tone={q.tone === "neutral" ? "neutral" : q.tone}>{q.label}</ColumnHead>
              <span className="font-mono text-[9px] uppercase tracking-[0.08em] text-muted-foreground">
                {q.state === "current" ? "now" : q.state}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <PaceRing
                // A quarter nobody has been asked to pay yet gets the dashed
                // "no reading" track, not a zero-length arc. Its `pct` really is
                // 0 — nothing of it has been collected — but rendering a bold
                // 0% next to "not due yet" is the exact misread this board
                // exists to prevent: the school has not asked, so there is no
                // score to report.
                pct={nothingBilled || nothingDue ? null : Math.min(100, q.pct ?? 0)}
                expectedPct={nothingBilled || nothingDue ? null : q.due_pct}
                tone={q.tone} size={62} stroke={7}>
                <span className="font-mono text-[12px] font-semibold leading-none tabular-nums">
                  {nothingBilled || nothingDue ? "—" : `${Math.round(q.pct ?? 0)}%`}
                </span>
              </PaceRing>
              <div className="min-w-0">
                <p className="font-mono text-[13px] tabular-nums">{shortMoney(q.collected)}</p>
                <p className="font-mono text-[10px] tabular-nums text-muted-foreground">
                  of {shortMoney(q.billed)}
                </p>
                <p className={`mt-0.5 text-[10px] leading-snug ${TONE_TEXT[q.tone] ?? ""}`}>
                  {caption}
                </p>
              </div>
            </div>
          </>
        );
        const cls = `rounded-xl border p-3 text-left transition-colors ${
          picked === q.label ? "border-primary/50 bg-accent/40" : "border-border bg-card"
        } ${onPick ? "hover:border-primary/40" : ""}`;
        return onPick ? (
          <button key={q.label} type="button" className={cls}
            aria-pressed={picked === q.label}
            onClick={() => onPick(q.label)}>{inner}</button>
        ) : (
          <div key={q.label} className={cls}>{inner}</div>
        );
      })}
    </div>
  );
}

/** The legend, said once per surface. The tick is the whole device and an
 *  unexplained mark on a ring is worse than no mark. */
export function PaceLegendFees({ className = "" }: { className?: string }) {
  return (
    <div className={`flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground ${className}`}>
      <span className="flex items-center gap-1.5">
        <i className="inline-block h-3 w-[2px] bg-foreground" /> due by today
      </span>
      <span>arc past the mark = paid ahead</span>
      <span>short of it = money not in</span>
    </div>
  );
}

/** Where the money is concentrated. `by_class` had seven numeric fields per row
 *  and was drawn as unsorted text — the eye cannot rank ten classes from that.
 *  Rows are ordered by families pending, because a morning of phone calls is
 *  denominated in calls, and both denominators ride along (`S-159`): ₹1.4L is
 *  one big defaulter or fourteen small ones, and those need opposite actions. */
export function ClassConcentration({ rows }: {
  rows: { class_id: string | null; class_label: string; families_pending: number;
    families_total: number; overdue: number; collected: number; billed: number;
    pct: number | null }[];
}) {
  if (!rows.length) return null;
  const worst = Math.max(...rows.map((r) => r.overdue), 1);
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1.4fr)] gap-3 border-b border-border bg-muted/25 px-4 py-2">
        <ColumnHead>Class</ColumnHead>
        <ColumnHead>Families pending</ColumnHead>
        <ColumnHead>Overdue</ColumnHead>
      </div>
      <ul className="divide-y divide-border/60">
        {rows.map((r) => (
          <li key={r.class_id ?? r.class_label}
            className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1.4fr)] items-center gap-3 px-4 py-2.5">
            <span className="truncate text-sm">{r.class_label}</span>
            <Fraction n={r.families_pending} of={r.families_total} />
            <span className="flex items-center gap-2">
              <span className="font-mono text-[12px] tabular-nums text-muted-foreground">
                {r.overdue > 0 ? money(r.overdue) : "—"}
              </span>
              <span className="relative h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
                {r.overdue > 0 ? (
                  <span className="absolute inset-y-0 left-0 rounded-full"
                    style={{ width: `${(r.overdue / worst) * 100}%`, background: "var(--chart-red)" }} />
                ) : null}
              </span>
            </span>
          </li>
        ))}
      </ul>
      <p className="border-t border-border bg-muted/25 px-4 py-2 text-[11px] text-muted-foreground">
        Bars are relative to the worst class, not to what it billed — this ranks where a
        morning of calls goes, not which class is poorest.
      </p>
    </div>
  );
}
