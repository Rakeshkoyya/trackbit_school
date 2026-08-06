"use client";

// One member of staff's record (V1-16) — where their time went.
//
// **This is a record, not an appraisal, and the screen has to say so before the
// reader decides for themselves.** `D-25`/`S-67` promised the person filling in
// the timesheet that it can neither rank them nor reach their pay; a screen
// titled "performance" with a big percentage on it breaks that promise in the
// first second, whatever the small print says. So there is no score anywhere on
// this page, no comparison to a colleague, no completion figure, and the month
// grid's ramp is keyed on *how full a day was*, never on how much was written
// down.
//
// The design continues the register: mono figures, a month you can find the
// 12th in, and `unmarked` as a texture rather than a colour. Three altitudes,
// the same three the timesheet itself uses (`D-18`/`S-64`) — **today** at full
// detail, **the month** as shape, and the **written summary** that reads both.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft, CalendarDays, ChevronLeft, ChevronRight, Moon, RefreshCw, Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { ChartCard, Donut, TrendLine } from "@/components/charts";
import { hueOf } from "@/components/insights/daybook";
import { ColumnHead, Empty, Fraction, Section } from "@/components/insights/shared";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { insightsApi } from "@/lib/insights-api";
import type { RecordDaySlot, RecordMonthDay, StaffRecord } from "@/lib/insights-types";
import { cn } from "@/lib/utils";

// ── month arithmetic ─────────────────────────────────────────────────────────

function shiftMonth(month: string, by: number): string {
  const [y, m] = month.split("-").map(Number);
  const total = y * 12 + (m - 1) + by;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, "0")}`;
}

const monthLabel = (month: string) =>
  new Date(`${month}-01T00:00:00`).toLocaleDateString("en-IN", {
    month: "long", year: "numeric",
  });

const dayNum = (iso: string) => Number(iso.slice(8, 10));

// ── the month grid ───────────────────────────────────────────────────────────

const WEEKDAYS = ["M", "T", "W", "T", "F", "S", "S"];

/**
 * The ramp. Sequential — ONE ink, light to dark — because the quantity is a
 * magnitude (periods in the day) and a magnitude drawn in several hues is a
 * quiz. The ink is the page's own foreground rather than a new colour, which is
 * what keeps this reading as a document and not a heatmap bolted onto one.
 *
 * `busy === 0` on a working day gets no fill at all. That is the load-bearing
 * step: a day with nothing on it is a day with nothing on it (`D-23`), and
 * shading it would put a mark on the page that means "this person did not write
 * anything down" — the exact figure `S-76` deleted.
 */
function rampFor(busy: number, max: number): string | undefined {
  if (busy <= 0) return undefined;
  const steps = [0.14, 0.3, 0.48, 0.68, 0.88];
  const idx = Math.min(steps.length - 1,
    Math.floor(((busy - 1) / Math.max(1, max)) * steps.length));
  return `color-mix(in oklab, var(--color-foreground) ${steps[idx] * 100}%, transparent)`;
}

function DayCell({ day, max }: { day: RecordMonthDay; max: number }) {
  // A day that has not happened is never shaded — the ramp means "this much was
  // worked", and filling the rest of the month makes a record read as a
  // forecast. A holiday that WAS worked keeps both its texture and its fill,
  // because an exam Saturday is a true thing about the month.
  const fill = day.state === "future" ? undefined : rampFor(day.busy, max);
  const parts = [
    `${day.date}`,
    day.state === "holiday" ? `Holiday — ${day.label ?? "school closed"}` : null,
    day.state === "leave" ? (day.label ?? "On leave") : null,
    day.state === "off" ? "Not a working day" : null,
    day.state === "future" ? "Still to come" : null,
    day.busy ? `${day.teaching} teaching · ${day.cover} covered · ${day.work} recorded` : null,
    day.state === "working" && !day.busy ? "Nothing on the timetable" : null,
  ].filter(Boolean);

  return (
    <div
      title={parts.join(" · ")}
      className={cn(
        "relative flex aspect-square items-start justify-end rounded-[3px] p-0.5 text-[9px]",
        // Every non-working state is a TEXTURE, never a colour: a holiday and a
        // busy day must not be told apart by hue alone, and a day off is not a
        //状態 anybody should have to decode from a shade.
        day.state === "off" && "bg-muted/40",
        day.state === "holiday" && "border border-dashed border-border",
        day.state === "leave" && "border border-border",
        day.state === "future" && "border border-dotted border-border/60",
        (day.state === "working" && !day.busy) && "border border-border/60",
      )}
      style={{
        ...(fill ? { background: fill } : {}),
        ...(day.state === "leave" ? {
          backgroundImage: "repeating-linear-gradient(135deg, transparent 0 3px, "
            + "color-mix(in oklab, var(--color-muted-foreground) 35%, transparent) 3px 5px)",
        } : {}),
      }}
    >
      <span className={cn("font-mono tabular-nums",
        day.busy >= max * 0.6 ? "text-card" : "text-muted-foreground/70")}>
        {dayNum(day.date)}
      </span>
    </div>
  );
}

/** The month as shape. Weekday columns so a date is findable — a bare 30-cell
 *  strip shows the same data and answers no question anybody has. */
function MonthGrid({ rec }: { rec: StaffRecord }) {
  const max = Math.max(1, ...rec.days.map((d) => d.busy));
  // Lead the first row with blanks so the 1st lands under its own weekday.
  const lead = rec.days.length ? rec.days[0].weekday : 0;

  return (
    <div>
      <div className="mb-1 grid grid-cols-7 gap-1">
        {WEEKDAYS.map((w, i) => (
          <span key={i}
            className="text-center font-mono text-[9px] uppercase tracking-widest text-muted-foreground">
            {w}
          </span>
        ))}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {Array.from({ length: lead }).map((_, i) => <span key={`lead-${i}`} />)}
        {rec.days.map((d) => <DayCell key={d.date} day={d} max={max} />)}
      </div>
      <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          Lighter
          {[1, 2, 3, 4, 5].map((n) => (
            <span key={n} className="h-2.5 w-2.5 rounded-[2px]"
              style={{ background: rampFor(n, 5) }} />
          ))}
          busier
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2.5 w-2.5 rounded-[2px] border border-dashed border-border" /> Holiday
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2.5 w-2.5 rounded-[2px] border border-border" /> Leave
        </span>
        <span className="inline-flex items-center gap-1">
          <span className="h-2.5 w-2.5 rounded-[2px] bg-muted/40" /> Not a working day
        </span>
      </div>
    </div>
  );
}

// ── today ────────────────────────────────────────────────────────────────────

/** The day as the person actually lived it: a vertical timeline with the clock
 *  down the side and the breaks in place, because a day with lunch missing from
 *  it is not the day anybody had. */
function TodayTimeline({ rec }: { rec: StaffRecord }) {
  if (!rec.today.length) {
    return <Empty>No periods on this day — the timetable has nothing for it.</Empty>;
  }
  const breakAfter = new Map(rec.today_breaks.map((b) => [b.period_no, b]));

  return (
    <ol className="space-y-1">
      {rec.today.map((slot) => (
        <li key={slot.period_no}>
          <Row slot={slot} />
          {breakAfter.has(slot.period_no) ? (
            <div className="my-1 flex items-center gap-2 pl-[62px]">
              <span className="h-px flex-1 bg-border" />
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                {breakAfter.get(slot.period_no)!.label} ·{" "}
                {breakAfter.get(slot.period_no)!.start}
              </span>
              <span className="h-px flex-1 bg-border" />
            </div>
          ) : null}
        </li>
      ))}
    </ol>
  );
}

function Row({ slot }: { slot: RecordDaySlot }) {
  const h = hueOf(slot.color);
  return (
    <div className="flex items-stretch gap-2">
      <div className="w-[54px] shrink-0 pt-1.5 text-right">
        <div className="font-mono text-[11px] font-medium tabular-nums">
          {String(slot.period_no).padStart(2, "0")}
        </div>
        {slot.start ? (
          <div className="font-mono text-[9px] tabular-nums text-muted-foreground">{slot.start}</div>
        ) : null}
      </div>
      <div
        className={cn(
          "min-w-0 flex-1 rounded-md px-3 py-2",
          slot.kind === "free" && "bg-muted/50",
          slot.kind === "away" && "border border-dashed border-border",
        )}
        style={h ? {
          background: `color-mix(in oklab, ${h} 13%, transparent)`,
          boxShadow: `inset 3px 0 0 0 ${h}`,
        } : undefined}
      >
        {slot.kind === "free" ? (
          <p className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground/70">
            Free
          </p>
        ) : slot.kind === "away" ? (
          <p className="text-[13px] text-muted-foreground">
            Away{slot.detail ? ` — ${slot.detail}` : ""}
          </p>
        ) : (
          <>
            <p className="truncate text-[13px] font-medium">
              {slot.label}
              {slot.kind === "cover" ? (
                <span className="ml-1.5 font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
                  covering
                </span>
              ) : null}
            </p>
            {slot.detail ? (
              <p className="truncate text-xs text-muted-foreground">{slot.detail}</p>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}

// ── figures ──────────────────────────────────────────────────────────────────

function Figure({
  label, value, of, sub,
}: {
  label: string;
  value: string | number;
  of?: string | number;
  sub?: string;
}) {
  return (
    <div className="min-w-0 flex-1 px-3 py-3">
      <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-lg font-semibold leading-none">
        {of != null
          ? <Fraction n={value} of={of} className="text-lg font-semibold" />
          : <span className="font-mono tabular-nums">{value}</span>}
      </p>
      {sub ? <p className="mt-1 text-[11px] leading-snug text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

// ── the page ─────────────────────────────────────────────────────────────────

const n = (v: number) => (Number.isInteger(v) ? String(v) : v.toFixed(1));

/** Below this, a trend line is drawing noise and implying a shape that is not
 *  there. The house rule elsewhere on this dashboard: not enough data is a
 *  WORD, never a chart with three points on it. */
const MIN_LINE_POINTS = 5;

export function StaffRecordView({ memberId }: { memberId: string }) {
  const qc = useQueryClient();
  const [month, setMonth] = useState<string | null>(null);
  const { data: rec, isLoading } = useQuery({
    queryKey: ["staff-record", memberId, month],
    queryFn: () => insightsApi.staffRecord(memberId, { month: month ?? undefined }),
    placeholderData: (prev) => prev,
  });
  const refresh = useMutation({
    mutationFn: async () => qc.invalidateQueries({ queryKey: ["staff-record", memberId] }),
  });

  if (isLoading && !rec) {
    return (
      <div className="space-y-4">
        <div className="h-24 animate-pulse rounded-xl border border-border bg-card" />
        <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />
      </div>
    );
  }
  if (!rec) return <Empty>That person is not on this school’s roll.</Empty>;

  const shown = month ?? rec.month;
  const total = rec.teaching_periods + rec.cover_periods + rec.work_periods;
  const series = rec.series.map((p) => ({
    x: String(dayNum(p.date)), teaching: p.teaching, work: p.work,
  }));

  return (
    <div>
      {/* Identity band. The role and the month are the two things that make
          every figure below it locatable. */}
      <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <Link href="/dashboard/staff"
            className="mb-1 inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <ArrowLeft className="h-3 w-3" /> Staff
          </Link>
          <h1 className="truncate text-xl font-semibold">{rec.name}</h1>
          <p className="mt-0.5 text-sm text-muted-foreground">
            {rec.role === "admin" ? "Admin staff" : "Teacher"} · a record of where the
            time went. No score, no ranking, and nothing here reaches pay.
          </p>
        </div>
        <div className="flex items-center gap-1 rounded-lg border border-border bg-card p-0.5">
          <button type="button" aria-label="Previous month"
            onClick={() => setMonth(shiftMonth(shown, -1))}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="min-w-[118px] text-center font-mono text-[12px]">
            {monthLabel(shown)}
          </span>
          <button type="button" aria-label="Next month"
            onClick={() => setMonth(shiftMonth(shown, 1))}
            className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* The written part leads, exactly as the dashboard's briefing does: the
          sentence is what a reader needs, the figures are what it rests on. */}
      <section className="mb-6 overflow-hidden rounded-xl border border-border bg-card">
        <div className="p-5">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
              <Sparkles className="h-3.5 w-3.5" /> The month in short
            </span>
            {rec.away_reason ? <Badge tone="warning">Away today</Badge> : null}
            <Button size="sm" variant="ghost" className="ml-auto" title="Read the figures again"
              onClick={() => refresh.mutate()} disabled={refresh.isPending}>
              <RefreshCw className={cn("h-3.5 w-3.5", refresh.isPending && "animate-spin")} />
            </Button>
          </div>
          <p className="max-w-[62ch] text-[15px] leading-relaxed">{rec.summary}</p>
          <p className="mt-2 max-w-[62ch] text-sm text-muted-foreground">{rec.headline}</p>
        </div>
        <div className="flex flex-wrap divide-x divide-border border-t border-border">
          <Figure label="Teaching" value={rec.teaching_periods}
            sub={rec.cover_periods ? `+ ${rec.cover_periods} covered for others` : "periods this month"} />
          <Figure label="Other work" value={rec.work_periods}
            sub="recorded on the timesheet" />
          <Figure label="Days worked" value={n(rec.days_present)} of={rec.working_days}
            sub={rec.days_not_marked
              ? `${rec.days_not_marked} day${rec.days_not_marked === 1 ? "" : "s"} not marked by the office`
              : "every working day marked"} />
          <Figure label="Leave" value={n(rec.leave_days)}
            sub={`${n(rec.leave_remaining)} left in the allowance`} />
        </div>
        <p className="border-t border-border bg-muted/25 px-5 py-2 text-xs text-muted-foreground">
          {rec.summary_source === "ai"
            ? "Written by TrackBit AI from the figures above — it is given no other information."
            : "Assembled from the figures above."}
        </p>
      </section>

      {/* Today, then the month. Today is what a conversation starts from. */}
      <div className="mb-6 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(300px,380px)]">
        <Section
          title={rec.is_today ? "Today" : "That day"}
          hint={rec.today_summary}
          className="mb-0"
        >
          <div className="rounded-xl border border-border bg-card p-4">
            <TodayTimeline rec={rec} />
            {rec.evening_labels.length ? (
              <p className="mt-3 flex items-center gap-1.5 border-t border-border pt-3 text-xs text-muted-foreground">
                <Moon className="h-3.5 w-3.5" />
                This evening: {rec.evening_labels.join(" · ")}
              </p>
            ) : null}
          </div>
        </Section>

        <Section title={monthLabel(shown)}
          hint="One cell per day. A day with nothing on it is a day with nothing on it — never a gap to be filled."
          className="mb-0">
          <div className="rounded-xl border border-border bg-card p-4">
            <MonthGrid rec={rec} />
            {rec.busiest_day ? (
              <p className="mt-3 border-t border-border pt-3 font-mono text-[11px] text-muted-foreground">
                Fullest day: {dayNum(rec.busiest_day)} {monthLabel(shown).split(" ")[0]} ·{" "}
                {rec.busiest_periods} periods
              </p>
            ) : null}
          </div>
        </Section>
      </div>

      {/* Where it went, and how it moved through the month. */}
      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <ChartCard title="Where the time went"
          hint={total ? `${total} recorded periods in ${monthLabel(shown)}.`
            : "Nothing recorded for this month yet."}>
          {rec.slices.length ? (
            <Donut
              size={150}
              unit="periods"
              centerValue={String(total)}
              centerLabel="periods"
              slices={rec.slices.map((s) => ({
                label: s.label, value: s.periods,
                color: hueOf(s.color) ?? "var(--color-muted)",
              }))}
            />
          ) : (
            <Empty>No periods recorded in this month.</Empty>
          )}
        </ChartCard>

        <ChartCard title="Through the month"
          hint="Teaching (including cover) beside the periods recorded as other work. School days only — plotting a Sunday as zero would draw a sawtooth that means nothing.">
          {series.length >= MIN_LINE_POINTS ? (
            <TrendLine rows={series} height={200} series={[
              { key: "teaching", label: "Teaching", color: "var(--chart-green)" },
              { key: "work", label: "Other work", color: hueOf(rec.slices[1]?.color ?? "slate")! },
            ]} />
          ) : (
            <Empty>
              {series.length
                ? `Only ${series.length} school day${series.length === 1 ? "" : "s"} so far this month — a line needs a few more before it means anything.`
                : "No school days in this month yet."}
            </Empty>
          )}
        </ChartCard>
      </div>

      {/* The template. Three named blocks, in this order and no other. */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Block title="Where the time went" tone="neutral" lines={rec.where_time_went}
          empty="Nothing recorded for this month." />
        <Block title="Notable" tone="green" lines={rec.highlights}
          empty="Nothing stands out yet this month." />
        <Block title="Worth a look" tone="amber" lines={rec.watch}
          empty="Nothing to flag — leave, lates and the attendance record are all clear." />
      </div>

      <p className="mt-4 flex items-start gap-1.5 text-xs text-muted-foreground">
        <CalendarDays className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        A period with nothing written against it is a free period, not a missing
        entry. Days the office never marked are counted separately and are never
        read as an absence.
      </p>
    </div>
  );
}

function Block({
  title, lines, empty, tone,
}: {
  title: string;
  lines: string[];
  empty: string;
  tone: "neutral" | "green" | "amber";
}) {
  const dot = { neutral: "bg-muted-foreground/40", green: "bg-success", amber: "bg-warning" }[tone];
  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <ColumnHead tone={tone}>{title}</ColumnHead>
      {lines.length ? (
        <ul className="mt-2.5 space-y-1.5">
          {lines.map((l, i) => (
            <li key={i} className="flex items-start gap-2 text-[13px] leading-snug">
              <span className={cn("mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full", dot)} />
              <span className="min-w-0">{l}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2.5 text-[13px] text-muted-foreground">{empty}</p>
      )}
    </section>
  );
}
