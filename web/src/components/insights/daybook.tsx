"use client";

// The day-book (V1-16) — the whole staff's day as one page.
//
// The visual thesis is the school's own artifact: a **register**, the ruled book
// a school office has kept for a hundred years. V1-14 established that language
// for presence (Geist Mono figures, uppercase tracked column heads, a dashed
// texture for "nobody wrote this down"); this is the same document, one spread
// further on. People down the left margin, periods across the head, and one
// mark per cell.
//
// Two decisions carry the whole grid, and both are product law rather than
// taste:
//
//   * **Only recorded work is coloured.** Teaching is the day's default state —
//     roughly seven cells in ten — so painting it a saturated hue makes a wall
//     of green that says nothing. It gets a quiet ink block; the timesheet's own
//     categories get the hues, because those cells are the only ones carrying a
//     fact the timetable did not already know. The eye lands on what the
//     timesheet ADDS, which is the only reason this board exists.
//   * **A free cell is the lightest mark on the page** (`D-23`). Not red, not
//     hatched, not a gap to be filled: an unfilled period IS a free one, and
//     `S-76` deleted a whole tile for forgetting that. An away cell is hatched
//     and a closed one fainter still — three emptinesses that a reader must be
//     able to tell apart, because "nobody was asked to work" and "somebody was
//     free" and "somebody was not in the building" are three different days.
//
// The palette is resolved server-side and its five category hues were run
// through the dataviz six-checks against both surfaces, in the ring order they
// are assigned in, together with the teaching ink they sit beside. Do not add a
// sixth by eye — see `core/work_types.py::CATEGORY_COLORS`.

import { ArrowRight, CalendarRange, ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { Donut } from "@/components/charts";
import type { Daybook, DaybookCell, DaybookRow } from "@/lib/insights-types";
import { cn } from "@/lib/utils";

import { ColumnHead, Empty, ScrollX } from "./shared";

// ── colour ───────────────────────────────────────────────────────────────────

/** The server's token → a paintable colour. `free` has none by design: the cell
 *  is drawn as bare surface, which is what a free period looks like. */
export function hueOf(color: string): string | null {
  if (color === "teaching") return "var(--chart-green)";
  if (color === "slate") return "var(--color-muted-foreground)";
  if (color === "free") return null;
  return color;
}

/** A light wash of the hue with the hue itself at full strength on the leading
 *  edge. The wash keeps a grid of forty cells calm and keeps the label legible
 *  on top of it; the edge is what you actually read the colour from, and it is
 *  the secondary encoding the palette's CVD floor is allowed on. */
function cellStyle(cell: DaybookCell): CSSProperties {
  const h = hueOf(cell.color);
  if (!h) return {};
  return {
    background: `color-mix(in oklab, ${h} 13%, transparent)`,
    boxShadow: `inset 3px 0 0 0 ${h}`,
  };
}

/** Covering someone else IS teaching — same ink, hatched, because it is not what
 *  the timetable planned. A second hue would say it was a different activity. */
const HATCH = "repeating-linear-gradient(135deg, transparent 0 4px, "
  + "color-mix(in oklab, var(--chart-green) 30%, transparent) 4px 6px)";

/**
 * Away, as a texture.
 *
 * Drawn first as a dashed 1px border, and the screenshot killed it: at a cell
 * 84px wide in dark mode a dashed hairline is indistinguishable from an empty
 * one, so the row of the person who was not in the building looked exactly like
 * the row of the person who was in it with nothing on. Those are the two facts
 * this board exists to separate, so the mark has to survive a glance.
 */
const AWAY_HATCH = "repeating-linear-gradient(45deg, transparent 0 5px, "
  + "color-mix(in oklab, var(--color-muted-foreground) 22%, transparent) 5px 7px)";

// ── one cell ─────────────────────────────────────────────────────────────────

function title(cell: DaybookCell): string {
  const what = [cell.label, cell.detail].filter(Boolean).join(" — ");
  if (cell.kind === "free") return `Period ${cell.period_no}: free`;
  if (cell.kind === "closed") return `Period ${cell.period_no}: not a working period`;
  if (cell.kind === "away") return `Period ${cell.period_no}: away${cell.detail ? ` — ${cell.detail}` : ""}`;
  if (cell.kind === "cover") return `Period ${cell.period_no}: covering ${what}`;
  return `Period ${cell.period_no}: ${what}`;
}

/**
 * Empty states carry no words in the grid.
 *
 * Written first with "FREE" and "AWAY" typed into every cell, and a screenshot
 * settled it: on any real day that is forty-odd repetitions of a word carrying
 * no information, shouting over the six cells that do. The three empties are
 * told apart by TEXTURE — a flat tint, a hatch, a fainter tint — which
 * is the encoding a colour-blind reader gets anyway, and every cell keeps its
 * tooltip while the row's own summary says "Away — Sick" once, in words.
 */
function Cell({ cell, locked }: { cell: DaybookCell; locked: boolean }) {
  const style = cellStyle(cell);
  const empty = cell.kind === "free" || cell.kind === "away" || cell.kind === "closed";
  return (
    <div
      title={title(cell)}
      className={cn(
        "flex min-w-0 flex-col justify-center rounded-[3px] px-2 py-1.5 text-left",
        empty && "min-h-[38px]",
        cell.kind === "free" && "bg-muted/60",
        cell.kind === "away" && "border border-border/70",
        // A period nobody was asked to work is the faintest thing on the page —
        // fainter than free, because it is not even an opportunity that existed.
        cell.kind === "closed" && "bg-muted/15",
        locked && "opacity-45",
      )}
      style={
        cell.kind === "cover" ? { ...style, backgroundImage: HATCH }
          : cell.kind === "away" ? { backgroundImage: AWAY_HATCH }
            : style
      }
    >
      {empty ? null : (
        <>
          <span className="truncate text-[12px] font-medium leading-tight">{cell.label}</span>
          {cell.detail ? (
            <span className="truncate text-[11px] leading-tight text-muted-foreground">
              {cell.detail}
            </span>
          ) : null}
          {cell.kind === "cover" ? (
            <span className="font-mono text-[9px] uppercase tracking-wider text-muted-foreground">
              covering
            </span>
          ) : null}
        </>
      )}
    </div>
  );
}

/** The compact form — no text, so the row reads as the SHAPE of a day. Used on
 *  the overview, where the question is "how full was today?" and the answer is
 *  a texture. Every square keeps its tooltip, and the legend below names the
 *  colours, so identity is never carried by hue alone. */
function MiniCell({ cell }: { cell: DaybookCell }) {
  const h = hueOf(cell.color);
  return (
    <span
      title={title(cell)}
      className={cn(
        "h-5 flex-1 rounded-[2px]",
        cell.kind === "free" && "bg-muted",
        cell.kind === "closed" && "bg-muted/25",
        cell.kind === "away" && "border border-border/70",
      )}
      style={cell.kind === "away" ? { backgroundImage: AWAY_HATCH } : h ? {
        background: `color-mix(in oklab, ${h} 22%, transparent)`,
        boxShadow: `inset 0 -2.5px 0 0 ${h}`,
        ...(cell.kind === "cover" ? { backgroundImage: HATCH } : {}),
      } : undefined}
    />
  );
}

// ── the grid ─────────────────────────────────────────────────────────────────

const ROLE_LABEL: Record<string, string> = { teacher: "Teachers", admin: "Admin staff" };

function groupByRole(rows: DaybookRow[]) {
  const order: string[] = [];
  const map = new Map<string, DaybookRow[]>();
  for (const r of rows) {
    if (!map.has(r.role)) { map.set(r.role, []); order.push(r.role); }
    map.get(r.role)!.push(r);
  }
  return order.map((role) => ({ role, rows: map.get(role)! }));
}

/**
 * The detailed board: the day, teacher by teacher, period by period.
 *
 * The first column is sticky because a name you have scrolled away from turns
 * the whole grid into anonymous colour — the one failure mode a wide table on a
 * laptop actually has.
 */
export function DaybookGrid({
  book, hrefFor,
}: {
  book: Daybook;
  hrefFor?: (row: DaybookRow) => string;
}) {
  const locked = new Set(book.locked_periods);
  if (!book.rows.length || !book.periods.length) {
    return <Empty>No timetable for this day yet, so there is no day to show.</Empty>;
  }
  // A named column for each period. `minmax(0, 1fr)` — not `1fr` — or a long
  // class label sets the column's min-content width and the grid stops
  // shrinking, which is what pushes a page into horizontal scroll.
  const cols = `minmax(160px, 1.4fr) repeat(${book.periods.length}, minmax(84px, 1fr))`;

  return (
    <ScrollX>
      <div className="min-w-[720px] overflow-hidden rounded-xl border border-border bg-card">
        {/* The head: period number over its clock, in mono. This is a document
            of record, and the times are what make a cell locatable in a day. */}
        <div className="sticky top-0 z-10 grid items-end gap-px border-b border-border bg-card px-1 pb-1.5 pt-2"
          style={{ gridTemplateColumns: cols }}>
          <div className="sticky left-0 z-10 bg-card px-2">
            <ColumnHead>Staff</ColumnHead>
          </div>
          {book.periods.map((p) => (
            <div key={p.period_no} className="px-1 text-center">
              <div className={cn("font-mono text-[11px] font-medium tabular-nums",
                locked.has(p.period_no) ? "text-muted-foreground/50" : "")}>
                {String(p.period_no).padStart(2, "0")}
              </div>
              {p.start ? (
                <div className="font-mono text-[9px] tabular-nums text-muted-foreground">
                  {p.start}
                </div>
              ) : null}
            </div>
          ))}
        </div>

        {groupByRole(book.rows).map(({ role, rows }) => (
          <div key={role}>
            <div className="border-y border-border bg-muted/30 px-3 py-1.5">
              <ColumnHead count={rows.length}>{ROLE_LABEL[role] ?? role}</ColumnHead>
            </div>
            {rows.map((row) => (
              <div key={row.member_id}
                className="grid items-stretch gap-px border-b border-border/50 px-1 py-1 last:border-0 hover:bg-muted/20"
                style={{ gridTemplateColumns: cols }}>
                <div className="sticky left-0 z-10 min-w-0 bg-card px-2 py-0.5">
                  {hrefFor ? (
                    <Link href={hrefFor(row)} className="block min-w-0 hover:underline">
                      <span className="block truncate text-[13px] font-medium">{row.name}</span>
                    </Link>
                  ) : (
                    <span className="block truncate text-[13px] font-medium">{row.name}</span>
                  )}
                  <span className="block truncate font-mono text-[10px] tracking-wide text-muted-foreground">
                    {row.summary}
                  </span>
                </div>
                {row.cells.map((c) => (
                  <Cell key={c.period_no} cell={c} locked={locked.has(c.period_no)} />
                ))}
              </div>
            ))}
          </div>
        ))}
      </div>
    </ScrollX>
  );
}

/** The overview's form: one row per person, squares only, and a link out. */
export function DaybookStrip({
  book, hrefFor,
}: {
  book: Daybook;
  hrefFor?: (row: DaybookRow) => string;
}) {
  if (!book.rows.length) {
    return <Empty>No timetable for this day yet, so there is no day to show.</Empty>;
  }
  return (
    <div className="space-y-1">
      {book.rows.map((row) => {
        const body = (
          <>
            <span className="w-[104px] shrink-0 truncate text-[12px] font-medium">{row.name}</span>
            <span className="flex min-w-0 flex-1 gap-0.5">
              {row.cells.map((c) => <MiniCell key={c.period_no} cell={c} />)}
            </span>
            {/* Words, not `5+2`. The first draft used a bare sum and a
                screenshot made the case against it: a two-number code needs a
                key the strip has no room for, and "5 cls" needs none. */}
            <span className="w-[62px] shrink-0 text-right font-mono text-[10px] tabular-nums text-muted-foreground"
              title={row.summary}>
              {row.away_reason ? "away"
                : row.teaching + row.cover > 0 ? `${row.teaching + row.cover} cls`
                  : row.work > 0 ? `${row.work} rec` : "—"}
            </span>
          </>
        );
        return hrefFor ? (
          <Link key={row.member_id} href={hrefFor(row)}
            className="flex items-center gap-2 rounded-md px-1 py-0.5 transition-colors hover:bg-muted/40">
            {body}
          </Link>
        ) : (
          <div key={row.member_id} className="flex items-center gap-2 px-1 py-0.5">{body}</div>
        );
      })}
    </div>
  );
}

/** The key. Present wherever the strip is, because the compact grid has no room
 *  for a label inside a cell and colour alone must never carry identity. */
export function DaybookLegend({ book }: { book: Daybook }) {
  const seen = new Map<string, string>();
  for (const row of book.rows) {
    for (const c of row.cells) {
      if (c.kind === "work" && c.label) seen.set(c.label, c.color);
    }
  }
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-[2px]"
          style={{
            background: "color-mix(in oklab, var(--chart-green) 22%, transparent)",
            boxShadow: "inset 0 -2.5px 0 0 var(--chart-green)",
          }} />
        Teaching
      </span>
      {[...seen].map(([label, color]) => {
        const h = hueOf(color);
        return (
          <span key={label} className="inline-flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-[2px]"
              style={h ? {
                background: `color-mix(in oklab, ${h} 22%, transparent)`,
                boxShadow: `inset 0 -2.5px 0 0 ${h}`,
              } : undefined} />
            {label}
          </span>
        );
      })}
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-[2px] bg-muted" /> Free
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-[2px] border border-border/70"
          style={{ backgroundImage: AWAY_HATCH }} /> Away
      </span>
      {/* Shown only when there is one on the page, so a normal Tuesday's key
          does not explain a state the reader cannot see. */}
      {book.rows.some((r) => r.cells.some((c) => c.kind === "closed")) ? (
        <span className="inline-flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-[2px] bg-muted/25" /> Not a working period
        </span>
      ) : null}
    </div>
  );
}

/**
 * How much of the school's day was spoken for.
 *
 * Part-to-whole of one known quantity — the day's staff period slots — so a ring
 * is the right form and the centre carries the only figure with no denominator
 * problem. The legend beside it is the chart: every slice arrives with its name
 * and its count, because six arcs read as six arcs and nothing more.
 *
 * The denominator excludes periods nobody could have worked (`S-72`), which is
 * why an absence makes the ring smaller rather than emptier.
 */
export function OccupancyRing({ book, size = 148 }: { book: Daybook; size?: number }) {
  if (!book.slices.length || !book.slots_total) {
    // Two different emptinesses, and saying the wrong one is how a board loses
    // its reader's trust: a shut school is not a school with no timetable.
    return (
      <Empty>
        {!book.is_working_day
          ? "No periods were expected on this day, so there is nothing to divide up."
          : "Nothing to divide up yet — no periods have been timetabled for this day."}
      </Empty>
    );
  }
  return (
    <Donut
      size={size}
      unit="periods"
      centerValue={book.occupied_pct == null ? "—" : `${book.occupied_pct}%`}
      centerLabel={book.occupied_pct == null ? "no denominator" : "spoken for"}
      slices={book.slices.map((s) => ({
        label: s.label,
        value: s.periods,
        color: hueOf(s.color) ?? "var(--color-muted)",
      }))}
    />
  );
}

// ── the date navigator ───────────────────────────────────────────────────────

const shift = (iso: string, by: number) => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + by);
  // Local Y-M-D, never `toISOString()` — east of UTC that returns the PREVIOUS
  // day for a local-midnight Date, which is the V1-14 bug this app already had.
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export const longDay = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", {
    weekday: "short", day: "numeric", month: "short",
  });

export function DayNav({
  date, onChange, today,
}: {
  date: string;
  onChange: (next: string) => void;
  today: string;
}) {
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-border bg-card p-0.5">
      <button type="button" aria-label="Previous day" onClick={() => onChange(shift(date, -1))}
        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
        <ChevronLeft className="h-4 w-4" />
      </button>
      <span className="min-w-[104px] text-center font-mono text-[12px] tabular-nums">
        {longDay(date)}
      </span>
      <button type="button" aria-label="Next day" onClick={() => onChange(shift(date, 1))}
        className="rounded-md p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
        <ChevronRight className="h-4 w-4" />
      </button>
      {date !== today ? (
        <button type="button" onClick={() => onChange(today)}
          className="ml-0.5 rounded-md px-2 py-1 text-[11px] font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground">
          Today
        </button>
      ) : null}
    </div>
  );
}

// ── the overview's block ─────────────────────────────────────────────────────

/**
 * The staff day, summarised for the overview.
 *
 * One block, two halves: the shape of everyone's day on the left, and what the
 * school's period capacity went on on the right. Both read from the same payload
 * the Staff tab renders in full, so the summary can never disagree with the
 * screen it links to.
 */
export function StaffDayBlock({
  book, loading, href = "/dashboard/staff",
}: {
  book: Daybook | undefined;
  loading?: boolean;
  href?: string;
}) {
  if (loading || !book) {
    return <div className="h-64 animate-pulse rounded-xl border border-border bg-card" />;
  }
  const more = book.rows_total != null ? book.rows_total - book.rows.length : 0;

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <header className="flex items-center gap-2 border-b border-border px-4 py-2.5">
        <span className="text-muted-foreground"><CalendarRange className="h-4 w-4" /></span>
        <h3 className="text-sm font-semibold">The staff day</h3>
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground">
          {longDay(book.date)}
        </span>
        <Link href={href}
          className="ml-auto inline-flex shrink-0 items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground">
          Open <ArrowRight className="h-3 w-3" />
        </Link>
      </header>

      <p className="px-4 pt-3 text-sm leading-relaxed">{book.headline}</p>

      {/* The ring column is deliberately wide: its legend IS the chart — six
          arcs read as six arcs and nothing more — and at 230px the category
          names truncated to "Noteboo…", which is the one thing a legend may
          never do. */}
      <div className="grid gap-5 p-4 xl:grid-cols-[minmax(0,1fr)_minmax(300px,360px)]">
        <div className="min-w-0 space-y-2.5">
          <DaybookStrip book={book} hrefFor={(r) => `/staff/member/${r.member_id}`} />
          {more > 0 ? (
            <Link href={href} className="block text-xs text-muted-foreground hover:underline">
              and {more} more {more === 1 ? "person" : "people"} →
            </Link>
          ) : null}
          <DaybookLegend book={book} />
        </div>
        <div className="min-w-0 border-t border-border pt-4 xl:border-l xl:border-t-0 xl:pl-5 xl:pt-0">
          <OccupancyRing book={book} size={128} />
        </div>
      </div>
    </section>
  );
}
