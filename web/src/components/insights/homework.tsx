"use client";

// V1-17 — homework, drawn as the funnel it actually is.
//
// The board used to open on four stat tiles and then draw the SAME measure
// three times: completion over the window, completion by class, completion by
// subject. Three charts, one number, and none of them said how much homework
// there was or whether anyone had looked at it. The three figures that matter
// were also in two different units — `assigned`/`checked` counted sets of
// homework and `done` counted students — so they could not be put on one track
// and did not read as one story.
//
// The device here is one track, three stages, all in student-homeworks:
//
//     GIVEN    1,240  ████████████████████████████████████████
//     CHECKED    922  ██████████████████████████▓▓▓▓▓▓▓▓▓▓▓▓▓▓
//     DID IT     806  ███████████████████████░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓
//
// The stages nest, so each gap is a length you can see. And the two gaps are
// two different findings, which is why they are drawn differently:
//
//   ▓  nobody has gone through it yet — HW-1's rule, the TEACHER's gap. It
//      wears the no-record hatch, the same texture an unmarked register cell
//      wears in V1-14 and an away cell wears in V1-16. Never a colour, never a
//      zero, never red. It sits in the same right-hand zone on both bars, so
//      the eye reads "this much of the page is simply unknown".
//   ░  checked, and not done. The only part of the shortfall that is about the
//      children, and the only part that may carry a judgement.
//
// Everything drawn here is a server figure. The component positions bars; it
// never decides what "low" means (that is `tone`, computed once in
// `services/homework.py`) and never divides anything (`completion` and
// `check_rate` arrive with their own denominators, deliberately named apart —
// "of what was given" and "of what has a verdict" are different facts).

import Link from "next/link";
import type { ReactNode } from "react";
import { NotebookPen } from "lucide-react";

import { ColumnHead, Empty, Fraction, ScrollX, StateChip } from "@/components/insights/shared";
import type { HomeworkBoard, OverviewSection } from "@/lib/insights-types";
import type {
  HomeworkDay,
  HomeworkFunnel,
  HomeworkMatrixCell,
  HomeworkScopeRow,
  TeacherCheckingRow,
} from "@/lib/school-types";

// The ordinal ramp, defined and validated in globals.css. Stage 3 is the
// deepest step in light mode and the brightest in dark — "more" reads as more
// ink on paper and more light on a screen.
const STAGE = ["var(--hw-stage-1)", "var(--hw-stage-2)", "var(--hw-stage-3)"] as const;

// The one no-record texture, shared with the day-book's away cells. 45° only.
// Pitch tightened from 5px to 4px after looking at it in light mode, where the
// looser weave read as an empty bar — and "nobody checked it" reading as
// "nothing there" is the one thing this texture exists to prevent.
const HATCH =
  "repeating-linear-gradient(45deg, var(--color-muted-foreground) 0 1px, transparent 1px 4px)";

/** The window the overview block reads, and it MUST match the one the server
 *  composes its sentence over (`HomeworkInsights.WINDOW_DAYS`). Fetching a
 *  different one put a 14-day sentence above a 7-day funnel — the block said
 *  "430 given" over bars reading 205. A constant, so the next person changing
 *  it changes it once. */
export const OVERVIEW_WINDOW_DAYS = 14;

export const num = (n: number) => n.toLocaleString("en-IN");
const pctOf = (part: number, whole: number) => (whole > 0 ? (part / whole) * 100 : 0);

/** One stage of the funnel: a bar whose fill is this stage and whose remainder
 *  is split into the part that is about the children and the part that is only
 *  a hole in the record. */
function StageBar({ fillPct, unknownFromPct, color, height = 10 }: {
  /** How far this stage reaches, as a share of stage 1. */
  fillPct: number;
  /** Where the no-record zone starts. Everything right of it is unchecked. */
  unknownFromPct: number;
  color: string;
  height?: number;
}) {
  const fill = Math.max(0, Math.min(100, fillPct));
  const unknown = Math.max(0, Math.min(100, unknownFromPct));
  return (
    <div className="relative w-full overflow-hidden rounded-full bg-muted" style={{ height }}>
      {/* The shortfall that IS about the work sits between the fill and the
          no-record zone, and is left as bare track — present, but never given a
          colour of its own, because a bar that shouts at a class is not what
          this board is for. */}
      {unknown < 100 ? (
        <div className="absolute inset-y-0 rounded-r-full opacity-70"
          style={{ left: `${unknown}%`, right: 0, backgroundImage: HATCH }} />
      ) : null}
      <div className="absolute inset-y-0 left-0 rounded-full transition-[width]"
        style={{ width: `${fill}%`, background: color }} />
    </div>
  );
}

/** The funnel. `dense` is the overview's copy of the same device — same rows,
 *  same rules, smaller type — so the block and the tab cannot disagree. */
export function StageTrack({ funnel, dense = false }: {
  funnel: HomeworkFunnel; dense?: boolean;
}) {
  const f = funnel;
  if (!f.given) {
    return <Empty>No homework has been set in this range. The stages fill in as teachers set and check work.</Empty>;
  }
  const didIt = f.done + f.late;
  const waiting = Math.max(0, f.given - f.checked);
  const checkedPct = pctOf(f.checked, f.given);
  const h = dense ? 8 : 12;

  const rows: { key: string; label: string; value: number; fill: number; color: string; sub: ReactNode }[] = [
    {
      key: "given", label: "Given", value: f.given, fill: 100, color: STAGE[0],
      sub: <>from {num(f.assignments)} set{f.assignments === 1 ? "" : "s"} across {f.class_subjects} class-subject{f.class_subjects === 1 ? "" : "s"}</>,
    },
    {
      key: "checked", label: "Teacher checked", value: f.checked, fill: checkedPct, color: STAGE[1],
      sub: f.check_rate == null ? "nothing to check yet" : (
        <>{Math.round(f.check_rate * 100)}% of what was given
          {waiting ? <> · <span className="text-foreground">{num(waiting)} still waiting</span></> : null}</>
      ),
    },
    {
      key: "done", label: "Students did it", value: didIt,
      fill: pctOf(didIt, f.given), color: STAGE[2],
      sub: f.completion == null
        ? "no verdict yet — this is unknown, not zero"
        : <>{Math.round(f.completion * 100)}% of the {num(f.graded)} with a verdict{f.late ? <> · {num(f.late)} late</> : null}</>,
    },
  ];

  return (
    <div className={dense ? "space-y-2.5" : "space-y-4"}>
      {rows.map((r) => (
        <div key={r.key}>
          <div className="flex items-baseline justify-between gap-3">
            <ColumnHead>{r.label}</ColumnHead>
            <span className={`font-mono tabular-nums ${dense ? "text-[15px]" : "text-[19px]"} font-semibold`}>
              {num(r.value)}
            </span>
          </div>
          <div className="mt-1.5">
            {/* Stage 1 has no unknown zone — everything given is, definitionally,
                given. Stages 2 and 3 share one, in the same place. */}
            <StageBar fillPct={r.fill} color={r.color} height={h}
              unknownFromPct={r.key === "given" ? 100 : checkedPct} />
          </div>
          <p className="mt-1 text-[11px] leading-snug text-muted-foreground">{r.sub}</p>
        </div>
      ))}
    </div>
  );
}

/** What sits between "checked" and "with a verdict", said in words.
 *  `carried` and `waived` leave the denominator entirely (D-34/S-98) — naming
 *  them is what stops them being silently absorbed into either gap. */
export function FunnelFootnote({ funnel }: { funnel: HomeworkFunnel }) {
  const f = funnel;
  const waiting = Math.max(0, f.given - f.checked);
  const bits: ReactNode[] = [];
  if (f.late) bits.push(<>{num(f.late)} handed in late, which counts as done</>);
  if (f.carried) bits.push(<>{num(f.carried)} were away when it was set</>);
  if (f.waived) bits.push(<>{num(f.waived)} let go by the teacher</>);
  if (waiting) bits.push(<>{num(waiting)} not gone through yet</>);
  if (!bits.length) return null;
  return (
    <p className="text-[11px] leading-relaxed text-muted-foreground">
      {bits.map((b, i) => <span key={i}>{i ? " · " : ""}{b}</span>)}
      {(f.carried || f.waived)
        ? <span className="block pt-0.5">Being away or being let off leaves the completion figure entirely — neither is a miss.</span>
        : null}
    </p>
  );
}

// ── the shape over time ──────────────────────────────────────────────────────

/** Stacked columns: did it · didn't · nobody checked. The height carries the
 *  VOLUME, which a completion line could not — a quiet Tuesday and a Tuesday
 *  where nothing came back drew as the same low point on the old chart.
 *
 *  Built in CSS rather than Recharts on purpose: it appears on the overview,
 *  where pulling in the charting chunk to draw fourteen rectangles would be the
 *  most expensive stack of bars in the product. */
export function LoadStrip({ days, height = 96, showLabels = true }: {
  days: HomeworkDay[]; height?: number; showLabels?: boolean;
}) {
  if (!days.length) {
    return <Empty>Nothing has been set in this range yet.</Empty>;
  }
  const peak = Math.max(...days.map((d) => d.given), 1);
  return (
    <div>
      <div className="flex items-end gap-[3px]" style={{ height }}>
        {days.map((d) => {
          const didIt = d.done;
          const missed = d.not_done + d.partial;
          const unchecked = d.not_checked;
          const scale = (n: number) => (n / peak) * height;
          const title = [
            `${d.label}: ${num(d.given)} given`,
            didIt ? `${num(didIt)} did it` : null,
            missed ? `${num(missed)} didn't` : null,
            unchecked ? `${num(unchecked)} not checked` : null,
          ].filter(Boolean).join(" · ");
          return (
            <div key={d.date} title={title}
              className="flex min-w-0 flex-1 flex-col justify-end gap-[2px]">
              {/* Order is bottom-up: what came back sits on the floor, what
                  nobody looked at floats on top — so the hatched band across
                  the top IS the checking backlog, read at a glance. */}
              {unchecked ? (
                <div className="w-full rounded-t-[3px] opacity-70"
                  style={{ height: scale(unchecked), backgroundImage: HATCH }} />
              ) : null}
              {missed ? (
                <div className="w-full"
                  style={{ height: scale(missed), background: "var(--chart-amber)" }} />
              ) : null}
              {didIt ? (
                <div className="w-full rounded-b-[3px]"
                  style={{ height: scale(didIt), background: STAGE[2] }} />
              ) : null}
              {!d.given ? <div className="h-[2px] w-full rounded-full bg-border" /> : null}
            </div>
          );
        })}
      </div>
      {showLabels ? (
        <div className="mt-1.5 flex gap-[3px]">
          {days.map((d, i) => (
            <span key={d.date}
              className="min-w-0 flex-1 truncate text-center font-mono text-[9px] uppercase tracking-[0.06em] text-muted-foreground">
              {/* A long range would smear its labels, so only every other one is
                  drawn once the buckets get thin. */}
              {days.length > 16 && i % 2 ? "" : d.label}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function LoadLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <i className="h-2.5 w-2.5 rounded-[2px]" style={{ background: STAGE[2] }} /> did it
      </span>
      <span className="flex items-center gap-1.5">
        <i className="h-2.5 w-2.5 rounded-[2px]" style={{ background: "var(--chart-amber)" }} /> didn&rsquo;t
      </span>
      <span className="flex items-center gap-1.5">
        <i className="h-2.5 w-2.5 rounded-[2px] opacity-70" style={{ backgroundImage: HATCH }} /> nobody checked
      </span>
    </div>
  );
}

// ── class × subject ──────────────────────────────────────────────────────────

const CELL_TONE: Record<string, string> = {
  green: "var(--chart-green)",
  amber: "var(--chart-amber)",
  red: "var(--chart-red)",
};

/** Where a low number actually lives. Two bar charts each collapsed a whole
 *  axis, so "6-B is low" and "Hindi is low" could never resolve into "6-B Hindi
 *  is where it happens" — the one thing an admin can act on.
 *
 *  A pair nobody checked is the hatch, not a red cell: the grid's worst-looking
 *  square must never be a hole in the record. */
export function ClassSubjectMatrix({ cells, classes, subjects }: {
  cells: HomeworkMatrixCell[]; classes: string[]; subjects: string[];
}) {
  if (!cells.length) return <Empty>No homework has been set yet — the grid fills in one class-subject at a time.</Empty>;
  const at = new Map(cells.map((c) => [`${c.class_key}||${c.subject_key}`, c]));
  const cols = `minmax(96px, 1.1fr) repeat(${subjects.length}, minmax(58px, 1fr))`;

  return (
    <div>
      <ScrollX>
        <div className="min-w-[560px]">
          <div className="grid items-end gap-px" style={{ gridTemplateColumns: cols }}>
            <div className="sticky left-0 z-10 bg-card pb-1.5 pr-2">
              <ColumnHead>Class</ColumnHead>
            </div>
            {subjects.map((s) => (
              <div key={s} className="pb-1.5 text-center">
                <span className="block truncate font-mono text-[10px] uppercase tracking-[0.08em] text-muted-foreground"
                  title={s}>{s}</span>
              </div>
            ))}
          </div>
          <div className="border-t border-border">
            {classes.map((c) => (
              <div key={c} className="grid items-center gap-px border-b border-border/60 py-1"
                style={{ gridTemplateColumns: cols }}>
                <div className="sticky left-0 z-10 truncate bg-card pr-2 font-mono text-[12px] tabular-nums">
                  {c}
                </div>
                {subjects.map((s) => {
                  const cell = at.get(`${c}||${s}`);
                  if (!cell) {
                    // The pair does not exist at all — not taught, not a gap.
                    return <div key={s} className="h-7 rounded-[3px] bg-muted/25" title={`${c} · ${s} — not taught`} />;
                  }
                  const unchecked = cell.completion == null;
                  const title = unchecked
                    ? `${c} · ${s} — ${num(cell.given)} given, none checked yet`
                    : `${c} · ${s} — ${Math.round((cell.completion ?? 0) * 100)}% of ${num(cell.graded)} with a verdict`;
                  return (
                    <div key={s} title={title}
                      className={`flex h-7 items-center justify-center rounded-[3px] transition-transform hover:scale-[1.08] ${
                        unchecked ? "border border-dashed border-muted-foreground/45" : ""}`}
                      style={unchecked ? undefined : {
                        // A wash, so a grid of these stays calm, with the tone
                        // at full strength only on the leading edge — the
                        // day-book's cell idiom, one spread further on.
                        background: `color-mix(in oklab, ${CELL_TONE[cell.tone]} 16%, transparent)`,
                        boxShadow: `inset 2px 0 0 0 ${CELL_TONE[cell.tone]}`,
                      }}>
                      <span className="font-mono text-[11px] tabular-nums text-foreground/80">
                        {unchecked ? "—" : Math.round((cell.completion ?? 0) * 100)}
                      </span>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </ScrollX>
      <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
        % done, of what has a verdict · <span className="border-b border-dashed border-muted-foreground/45">dashed</span> = given, nobody checked · faint = not taught
      </p>
    </div>
  );
}

// ── who is checking ──────────────────────────────────────────────────────────

/** Denominated in SETS, deliberately — "she set nine and went through four" is
 *  the sentence, and it is about her own act. Teachers are never ranked by
 *  their students' completion here: that would make a teacher's score a
 *  function of children's behaviour, which is what D-39/S-92 keep out of this
 *  module. */
export function CheckingLedger({ rows }: { rows: TeacherCheckingRow[] }) {
  if (!rows.length) return <Empty>Nobody has set homework in this range.</Empty>;
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="hidden grid-cols-[minmax(0,2fr)_repeat(3,minmax(0,1fr))_minmax(90px,1.2fr)] gap-2 border-b border-border bg-muted/25 px-4 py-2 sm:grid">
        <ColumnHead>Teacher</ColumnHead>
        <ColumnHead>Set</ColumnHead>
        <ColumnHead>Checked</ColumnHead>
        <ColumnHead>Overdue</ColumnHead>
        <ColumnHead>Rate</ColumnHead>
      </div>
      <ul className="divide-y divide-border/60">
        {rows.map((t) => (
          <li key={t.member_id ?? t.teacher_name}
            className="grid grid-cols-1 gap-1.5 px-4 py-2.5 sm:grid-cols-[minmax(0,2fr)_repeat(3,minmax(0,1fr))_minmax(90px,1.2fr)] sm:gap-2 sm:items-center">
            <span className="truncate text-sm">{t.teacher_name}</span>
            {/* Below `sm` the column heads are gone, so each figure carries its
                own word inline. Three bare numbers under a name is a row that
                cannot be read at all on the device most of this is read on. */}
            <span className="font-mono text-[13px] tabular-nums">
              <span className="mr-1 text-[10px] uppercase tracking-[0.1em] text-muted-foreground sm:hidden">set</span>
              {t.assigned}
            </span>
            <span className="font-mono text-[13px] tabular-nums">
              <span className="mr-1 text-[10px] uppercase tracking-[0.1em] text-muted-foreground sm:hidden">checked</span>
              {t.checked}
            </span>
            <span className={`font-mono text-[13px] tabular-nums ${
              t.unchecked_overdue ? "text-danger" : "text-muted-foreground"}`}>
              <span className="mr-1 text-[10px] uppercase tracking-[0.1em] text-muted-foreground sm:hidden">overdue</span>
              {t.unchecked_overdue}
            </span>
            <span className="sm:col-span-1">
              {t.check_rate == null ? <StateChip>nothing set</StateChip> : (
                <span className="flex items-center gap-2">
                  <span className="font-mono text-[12px] tabular-nums text-muted-foreground">
                    {Math.round(t.check_rate * 100)}%
                  </span>
                  <span className="relative h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-muted">
                    <span className="absolute inset-y-0 left-0 rounded-full"
                      style={{
                        width: `${Math.round(t.check_rate * 100)}%`,
                        background: t.check_rate >= 0.8 ? "var(--chart-green)"
                          : t.check_rate >= 0.5 ? "var(--chart-amber)" : "var(--chart-red)",
                      }} />
                  </span>
                </span>
              )}
            </span>
          </li>
        ))}
      </ul>
      <p className="border-t border-border bg-muted/25 px-4 py-2 text-[11px] text-muted-foreground">
        Counted in sets of homework, and &ldquo;overdue&rdquo; only once the deadline has passed —
        homework set an hour ago is not a failure to check.
      </p>
    </div>
  );
}

// ── best and worst, where it is fair to name one ─────────────────────────────

/** Classes and subjects get a best/worst; people do not. A class or a subject
 *  is a place, and pointing at a place starts a conversation. Ranking teachers
 *  by their children's completion would make a person's standing a function of
 *  forty other people's evenings — the checking ledger above is the teacher's
 *  own act, and that is the only thing this module rates them on. */
export function ScopeRank({ rows, title, hint, href }: {
  rows: HomeworkScopeRow[]; title: string; hint: string; href?: (r: HomeworkScopeRow) => string;
}) {
  const rated = rows.filter((r) => r.completion != null);
  if (rated.length < 2) {
    return (
      <div className="rounded-xl border border-border bg-card p-4">
        <p className="text-sm font-semibold">{title}</p>
        <p className="mt-2 text-[13px] text-muted-foreground">
          {rated.length ? "Only one has been checked so far — a best and a worst need two." : "Nothing checked yet."}
        </p>
      </div>
    );
  }
  const sorted = [...rated].sort((a, b) => (b.completion ?? 0) - (a.completion ?? 0));
  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="border-b border-border px-4 py-2.5">
        <p className="text-sm font-semibold">{title}</p>
        <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p>
      </div>
      <ul className="divide-y divide-border/60">
        <RankRow r={sorted[0]} kind="best" href={href} />
        <RankRow r={sorted[sorted.length - 1]} kind="worst" href={href} />
      </ul>
    </div>
  );
}

function RankRow({ r, kind, href }: {
  r: HomeworkScopeRow; kind: "best" | "worst"; href?: (r: HomeworkScopeRow) => string;
}) {
  const body = (
    <div className="flex items-baseline justify-between gap-3">
      <span className="min-w-0 truncate text-sm">{r.key}</span>
      <span className="shrink-0">
        <span className={`font-mono text-[15px] font-semibold tabular-nums ${
          kind === "best" ? "text-success" : "text-danger"}`}>
          {Math.round((r.completion ?? 0) * 100)}%
        </span>
        <span className="ml-2 text-muted-foreground">
          <Fraction n={r.done + r.late} of={r.students_expected} className="text-[11px]" />
        </span>
      </span>
    </div>
  );
  return (
    <li className="px-4 py-2.5">
      <ColumnHead tone={kind === "best" ? "green" : "red"}>
        {kind === "best" ? "Highest" : "Lowest"}
      </ColumnHead>
      <div className="mt-1">
        {href ? <Link href={href(r)} className="block hover:underline">{body}</Link> : body}
      </div>
    </li>
  );
}

// ── the overview block ───────────────────────────────────────────────────────

/** Homework on the dashboard: the sentence, the funnel, the week's shape, and
 *  the few named rows waiting on somebody — each linking to the screen that
 *  clears it.
 *
 *  It renders the SAME `StageTrack` the tab renders, at a smaller size, off the
 *  same server figures. That is the point: the block and the tab are one
 *  computation with two renderings, so the summary can never quote a number the
 *  screen it links to disagrees with.
 *
 *  The headline and the named rows are the server's, not this component's — a
 *  block that picked its own three rows would be a second opinion about what is
 *  worth saying. */
export function HomeworkOverviewBlock({ section, board, loading }: {
  section?: OverviewSection;
  board?: HomeworkBoard;
  loading?: boolean;
}) {
  if (loading && !board) {
    return <div className="h-72 animate-pulse rounded-xl border border-border bg-card" />;
  }
  if (!board || !section) return null;
  const f = board.overview.funnel;
  const more = Math.max(0, section.notes_total - section.notes.length);

  return (
    <section className={`overflow-hidden rounded-xl border bg-card ${
      section.tone === "red" ? "border-danger/35"
        : section.tone === "amber" ? "border-warning/35" : "border-border"}`}>
      <header className="flex items-center gap-2 border-b border-border px-4 py-2.5">
        <NotebookPen className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold">Homework</h3>
        {section.tone === "red" || section.tone === "amber" ? (
          <span className={`h-1.5 w-1.5 rounded-full ${
            section.tone === "red" ? "bg-danger" : "bg-warning"}`} />
        ) : null}
        <Link href="/dashboard/homework"
          className="ml-auto text-xs text-muted-foreground hover:text-foreground">
          Open &rarr;
        </Link>
      </header>

      <p className="px-4 pt-3 text-sm leading-relaxed">{section.headline}</p>

      <div className="grid gap-4 px-4 py-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <StageTrack funnel={f} dense />
        <div className="min-w-0">
          <div className="mb-2 flex items-baseline justify-between gap-2">
            {/* Taken from the payload, never from how many buckets came back:
                a window with three quiet days is still a fortnight. */}
            <ColumnHead>Last {board.overview.window_days} days</ColumnHead>
          </div>
          <LoadStrip days={board.daily} height={84} showLabels={false} />
          <div className="mt-2">
            <LoadLegend />
          </div>
        </div>
      </div>

      {section.notes.length ? (
        <ul className="border-t border-border bg-muted/25">
          {section.notes.map((n, i) => (
            <li key={i} className="border-b border-border/50 last:border-b-0">
              {n.href ? (
                <Link href={n.href} className="flex items-start gap-2 px-4 py-2 hover:bg-muted/40">
                  <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                    n.tone === "red" ? "bg-danger" : n.tone === "amber" ? "bg-warning" : "bg-muted-foreground"}`} />
                  <span className="text-[13px] leading-snug">{n.text}</span>
                </Link>
              ) : (
                <span className="flex items-start gap-2 px-4 py-2">
                  <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                    n.tone === "red" ? "bg-danger" : n.tone === "amber" ? "bg-warning" : "bg-muted-foreground"}`} />
                  <span className="text-[13px] leading-snug">{n.text}</span>
                </span>
              )}
            </li>
          ))}
          {more ? (
            <li>
              <Link href="/dashboard/homework"
                className="flex items-center justify-center gap-1.5 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground hover:text-foreground">
                {/* One string, so the letter-spacing cannot swallow the space
                    and render "+8MORE". */}
                <span>{`+${more} more`}</span>
                <span aria-hidden>&rarr;</span>
              </Link>
            </li>
          ) : null}
        </ul>
      ) : (
        <p className="border-t border-border bg-muted/25 px-4 py-2.5 text-[13px] text-muted-foreground">
          Nobody is repeatedly missing homework and everyone is going through what they set.
        </p>
      )}
    </section>
  );
}

// ── the range filter ─────────────────────────────────────────────────────────

export const RANGES = [
  { key: "week", label: "Week", days: 7 },
  { key: "month", label: "Month", days: 30 },
  { key: "term", label: "Term", days: 120 },
  { key: "year", label: "Year", days: 365 },
] as const;

export type RangeKey = (typeof RANGES)[number]["key"];

/** One filter row above everything it scopes — never a control inside a chart
 *  card, so every figure on the screen is always the same slice. */
export function RangeSwitch({ value, onChange }: {
  value: RangeKey; onChange: (next: RangeKey) => void;
}) {
  return (
    <div className="flex gap-1 rounded-lg border border-border p-0.5">
      {RANGES.map((r) => (
        <button key={r.key} type="button" onClick={() => onChange(r.key)}
          aria-pressed={value === r.key}
          className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
            value === r.key ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:text-foreground"}`}>
          {r.label}
        </button>
      ))}
    </div>
  );
}
