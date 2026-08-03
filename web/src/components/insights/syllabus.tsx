"use client";

// V1-15 — the syllabus panorama.
//
// THE DESIGN, and why it is this.
//
// A syllabus percentage on its own cannot be read. 47% is excellent in July and
// alarming in February, and nobody carries the school calendar in their head
// while glancing at a dashboard — so the old board answered "how much?" and left
// "is that good?" to a RAG chip three columns away. Every figure here is drawn
// on a track that also carries **the plan's own marker**: the share the approved
// plan had scheduled by today. The verdict becomes a distance you can see. Arc
// past the tick is ahead; arc short of it is behind; the gap is the size of the
// problem. The number stops being a riddle and becomes a detail.
//
// That one device repeats at three scales — the school ring, a row's bar, a
// matrix cell — so a single visual habit reads the whole module. It is the
// drawing-side of the law the module is built on: one computation, many
// renderings.
//
// Typography follows V1-14's register: Geist Mono for every figure, denominator
// and column head, because these boards are documents of record and read like
// one. The prose stays in the body face.
//
// Four rules the pixels must keep, all inherited and none negotiable:
//   * `unplanned` / `unallocated` / `unestimated` / `unknown` are STATES. Words
//     in a neutral chip, a dashed track — never a step on the RAG scale.
//   * a subject nobody logged a lesson against is not doing well. It is
//     unobserved: neutral, with the word, never green and never red (`S-42`).
//   * every figure carries its denominator, and the two bases name themselves —
//     "of the plan" and "of the whole syllabus" answer different questions
//     (`S-51`). A marker is only ever drawn against the figure it shares a
//     denominator with.
//   * nothing here computes a percentage. Tone, caption, marker and order all
//     arrive from `services/insights/syllabus.py`.

import { ArrowRight } from "lucide-react";
import Link from "next/link";

import { PaceBar, PaceRing, STATUS_COLOR } from "@/components/charts";
import type {
  CauseTally, SyllabusNode, SyllabusPulse, SyllabusRow, SyllabusScope, TermOption,
} from "@/lib/insights-types";
import { cn } from "@/lib/utils";

import { ColumnHead, Empty, Fraction, StateChip, TONE_DOT, type Tone } from "./shared";

/** green/amber/red are pace; every other status is a state and gets a word. */
export function toneForStatus(status: string): Tone {
  return status === "green" ? "green"
    : status === "amber" ? "amber"
      : status === "red" ? "red" : "neutral";
}

export const CAUSE_LABEL: Record<string, string> = {
  not_logged: "nothing logged",
  periods_lost: "periods lost",
  never_sized: "chapters not sized",
  slower: "behind on teaching",
};

const CAPTION_TONE: Record<Tone, string> = {
  neutral: "text-muted-foreground",
  green: "text-muted-foreground",
  amber: "text-warning",
  red: "text-danger",
};

/**
 * What the tick means, said once per surface.
 *
 * The marker is the whole device, and a device nobody has been told about is
 * decoration. It is one line of text, it sits under the first thing that draws
 * a tick, and it never repeats on the same screen.
 */
export function PaceLegend({ className = "" }: { className?: string }) {
  return (
    <p className={cn("flex items-start gap-1.5 text-[11px] leading-snug text-muted-foreground",
      className)}>
      <span className="mt-[3px] inline-block h-2.5 w-[2px] shrink-0 rounded-full bg-foreground" />
      <span>The mark on each track is where the approved plan said teaching
        would be by today.</span>
    </p>
  );
}

// ── the term switch ──────────────────────────────────────────────────────────

/**
 * Whole year, or one term.
 *
 * The options come down with the payload, so the running term is decided
 * against the school's clock rather than the browser's — a school in one
 * timezone and an owner travelling in another must not see different terms
 * highlighted. A school with no terms gets nothing at all rather than a
 * disabled control explaining an absence.
 */
export function TermSwitch({
  terms, value, onChange, className = "",
}: {
  terms: TermOption[];
  value: string;
  onChange: (id: string) => void;
  className?: string;
}) {
  if (!terms.length) return null;
  return (
    <label className={cn("inline-flex items-center gap-1.5", className)}>
      <span className="sr-only">Narrow to a term</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-border bg-card px-2 py-1 font-mono text-[11px] tracking-wide text-foreground">
        <option value="">Whole year</option>
        {terms.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name}{t.is_current ? " · now" : ""}
          </option>
        ))}
      </select>
    </label>
  );
}

// ── a list of nodes as pace bars ─────────────────────────────────────────────

/**
 * One breakdown — by class, by subject, by teacher.
 *
 * Worst first, because the point of a capped list on a summary is that the rows
 * nobody would scroll to are the ones shown. The order is the server's: it ranks
 * on topics genuinely behind, which is a figure a person can check by hand.
 */
export function NodeBarList({
  nodes, limit, href, basis = "syllabus", emptyLabel,
}: {
  nodes: SyllabusNode[];
  limit?: number;
  href?: string;
  /** Which denominator the bars are drawn on. The marker follows it. */
  basis?: "syllabus" | "planned";
  emptyLabel?: string;
}) {
  const shown = limit ? nodes.slice(0, limit) : nodes;
  const hidden = nodes.length - shown.length;

  if (!shown.length) {
    return (
      <p className="px-4 py-3 text-[11px] leading-snug text-muted-foreground">
        {emptyLabel ?? "Nothing to show yet."}
      </p>
    );
  }

  return (
    <div>
      <ul>
        {shown.map((n) => {
          const pct = basis === "planned" ? n.coverage_pct : n.syllabus_pct;
          const mark = basis === "planned" ? n.expected_pct : n.expected_syllabus_pct;
          return (
            <li key={n.key}
              className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2.5 gap-y-1 border-t border-border/60 px-4 py-2 first:border-t-0">
              <span className="truncate text-[13px]" title={n.label}>{n.label}</span>
              <span className="font-mono text-[12px] tabular-nums">
                {pct != null ? `${pct}%`
                  : <span className="text-[10px] uppercase tracking-wide text-muted-foreground">n/a</span>}
              </span>
              <span className="col-span-2">
                <PaceBar pct={pct} expectedPct={mark} tone={n.tone} height={6} />
              </span>
            </li>
          );
        })}
      </ul>
      {hidden > 0 && href ? (
        <Link href={href}
          className="block border-t border-border/60 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground hover:text-foreground">
          +{hidden} more
        </Link>
      ) : null}
    </div>
  );
}

// ── the overview's block ─────────────────────────────────────────────────────

/**
 * The syllabus, on the dashboard overview: one ring and two breakdowns.
 *
 * It replaces the module card that used to sit in the grid — three one-number
 * tiles that could say "78% on track" and never which class, which subject, or
 * whether that was good for the second week of August. The ring answers *how
 * far*, the marker answers *is that good*, and the two lists answer *who*.
 *
 * Everything is drawn on the whole-syllabus denominator, deliberately: it is the
 * one that cannot fall when next term's chapters are sized (`S-54`), so a school
 * doing its planning properly never watches this block go backwards. The
 * plan-basis figure is on the tab, where there is room to name both.
 */
export function SyllabusPulseBlock({
  pulse, termId, onTerm, loading,
}: {
  pulse: SyllabusPulse | undefined;
  termId: string;
  onTerm: (id: string) => void;
  loading?: boolean;
}) {
  if (loading) {
    return <div className="h-[268px] animate-pulse rounded-xl border border-border bg-card" />;
  }
  // A failed read must not shimmer forever. `isLoading` goes false on error and
  // the data never arrives, so without this the block is a permanent skeleton —
  // indistinguishable from a slow server, and the one state that tells nobody
  // anything. Say what is missing and leave the way through to the tab open.
  if (!pulse) {
    return (
      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <header className="flex items-center gap-2 border-b border-border px-4 py-2.5">
          <ColumnHead>Syllabus</ColumnHead>
          <Link href="/dashboard/syllabus"
            className="ml-auto inline-flex shrink-0 items-center gap-1 font-mono text-[10px] uppercase tracking-[0.1em] text-primary hover:underline">
            Details <ArrowRight className="h-3 w-3" />
          </Link>
        </header>
        <p className="px-4 py-5 text-[13px] text-muted-foreground">
          The syllabus figures could not be loaded just now. The board itself is
          still there.
        </p>
      </section>
    );
  }
  const school = pulse.school;

  return (
    <section className="overflow-hidden rounded-xl border border-border bg-card">
      <header className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-border px-4 py-2.5">
        <ColumnHead tone={school?.tone ?? "neutral"}>Syllabus</ColumnHead>
        {pulse.term_label ? (
          <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
            {pulse.term_label}
          </span>
        ) : null}
        <div className="ml-auto flex items-center gap-2">
          <TermSwitch terms={pulse.terms} value={termId} onChange={onTerm} />
          <Link href="/dashboard/syllabus"
            className="inline-flex shrink-0 items-center gap-1 font-mono text-[10px] uppercase tracking-[0.1em] text-primary hover:underline">
            Details <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </header>

      <p className="px-4 pt-3.5 text-[13px] leading-relaxed">{pulse.headline}</p>

      <div className="grid gap-x-4 gap-y-5 px-4 pb-4 pt-4 md:grid-cols-[auto_minmax(0,1fr)_minmax(0,1fr)]">
        {/* The ring. Its centre is the number; its tick is the verdict. */}
        <div className="flex flex-col items-center justify-self-center">
          <PaceRing pct={school?.syllabus_pct ?? null}
            expectedPct={school?.expected_syllabus_pct ?? null}
            tone={school?.tone ?? "neutral"} size={132} stroke={12}
            label="Syllabus taught, whole school">
            {school && school.syllabus_pct != null ? (
              <>
                <span className="font-mono text-[26px] font-semibold leading-none tabular-nums">
                  {Math.round(school.syllabus_pct)}
                  <span className="text-[13px] text-muted-foreground">%</span>
                </span>
                <span className="mt-1.5 max-w-[84px] text-center font-mono text-[9px] uppercase leading-tight tracking-[0.1em] text-muted-foreground">
                  of the portion
                </span>
              </>
            ) : (
              <span className="max-w-[86px] text-center text-[11px] leading-tight text-muted-foreground">
                no portion sized yet
              </span>
            )}
          </PaceRing>

          {school ? (
            <p className="mt-3 text-center">
              <Fraction n={school.taught_topics} of={school.total_topics}
                className="text-[13px]" />
              <span className="mt-0.5 block font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground">
                topics taught
              </span>
            </p>
          ) : null}
          {school?.pace_caption ? (
            <p className={cn("mt-2 max-w-[150px] text-center text-[11px] leading-snug",
              CAPTION_TONE[school.tone])}>
              {school.pace_caption}
            </p>
          ) : null}
        </div>

        {/* The two breakdowns. Same device, one scale down. */}
        {([
          { key: "classes", label: "By class", nodes: pulse.classes,
            empty: "No class has a syllabus yet." },
          { key: "subjects", label: "By subject", nodes: pulse.subjects,
            empty: "No subject has a syllabus yet." },
        ] as const).map((col) => (
          <div key={col.key} className="min-w-0 overflow-hidden rounded-lg border border-border">
            <div className="border-b border-border bg-muted/25 px-4 py-1.5">
              <ColumnHead count={col.nodes.length}>{col.label}</ColumnHead>
            </div>
            <NodeBarList nodes={col.nodes} limit={5} href="/dashboard/syllabus"
              emptyLabel={col.empty} />
          </div>
        ))}
      </div>

      <div className="border-t border-border bg-muted/25 px-4 py-2">
        <PaceLegend />
      </div>
    </section>
  );
}

// ── the portion, split into states ───────────────────────────────────────────

/**
 * Where the whole portion stands — finished, part-taught, not started.
 *
 * The board has never drawn this, and it is the question an owner actually asks
 * in April. A weighted percentage cannot answer it: 12.5 topics is 12 finished
 * plus one half-done or 11 plus three, and the difference is a fortnight of
 * teaching. The three counts are disjoint and all three arrive from the server.
 *
 * Unsized chapters ride along as an ANNOTATION, not a fourth segment: they are
 * already inside the portion, and giving them their own slice would count them
 * twice while making "not sized" look like a stage of teaching.
 */
export function PortionMeter({ node }: { node: SyllabusNode }) {
  const parts = [
    { key: "full", value: node.taught_full, color: STATUS_COLOR.green,
      label: "Finished" },
    { key: "partial", value: node.taught_partial, color: STATUS_COLOR.amber,
      label: "Part-taught" },
    { key: "untaught", value: node.untaught_topics, color: "var(--color-muted)",
      label: "Not started" },
  ];
  const total = node.total_topics;

  if (!total) {
    return <Empty>No chapters have been entered yet — the portion appears once
      the syllabus is imported.</Empty>;
  }

  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-full bg-muted">
        {parts.map((p, i) => p.value > 0 ? (
          <div key={p.key} title={`${p.label}: ${p.value} of ${total} topics`}
            style={{
              width: `${(p.value / total) * 100}%`,
              background: p.color,
              marginRight: i < parts.length - 1 ? 2 : 0,
            }} />
        ) : null)}
      </div>
      <ul className="mt-3 grid gap-x-4 gap-y-2 sm:grid-cols-3">
        {parts.map((p) => (
          <li key={p.key} className="flex items-baseline gap-2">
            <span className="mt-1 h-2 w-2 shrink-0 rounded-full"
              style={{ background: p.color }} />
            <span className="min-w-0 flex-1">
              <span className="block font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground">
                {p.label}
              </span>
              <Fraction n={p.value} of={total} className="text-[15px]" />
            </span>
          </li>
        ))}
      </ul>
      {node.unestimated_topics > 0 ? (
        <p className="mt-3 border-t border-border pt-2.5 text-[11px] leading-snug text-muted-foreground">
          <span className="font-mono tabular-nums text-foreground">
            {node.unestimated_topics}
          </span>{" "}
          of these {node.unestimated_topics === 1 ? "chapters has" : "chapters have"} no
          estimate, so {node.unestimated_topics === 1 ? "it is" : "they are"} in the
          portion but never scheduled.{" "}
          <Link href="/plan/syllabus" className="text-primary hover:underline">
            Size them
          </Link>
        </p>
      ) : null}
    </div>
  );
}

// ── S-41, counted ────────────────────────────────────────────────────────────

/**
 * Why the school is behind — capture, calendar, sizing, or teaching.
 *
 * The single most useful thing on this board, and the reason is arithmetic no
 * chart can do: "6 subjects behind" is one finding, and "4 of those 6 are behind
 * because nobody wrote a lesson log" is a completely different one that no
 * amount of talking to teachers about pace will fix.
 *
 * Empty causes are kept. *"Nothing lost to cancelled periods"* is a finding, and
 * a tally that drops its zeroes makes the survivors look like the whole story.
 */
export function CauseSplit({ causes }: { causes: CauseTally[] }) {
  const total = causes.reduce((sum, c) => sum + c.count, 0);

  if (!total) {
    return (
      <Empty>
        Nothing is behind its plan — no cause to attribute.
      </Empty>
    );
  }

  // Only the last cause is about teaching, so only the last one reads as a
  // warning — a capture gap is not a failing grade for anybody. But three
  // neutrals side by side in one fill are one indistinguishable bar, so they
  // step down in weight in the fixed order: a sequence, which is what they are,
  // rather than four competing hues fighting the RAG palette for meaning.
  const tone: Record<string, Tone> = {
    not_logged: "neutral", periods_lost: "neutral",
    never_sized: "neutral", slower: "amber",
  };
  const FILL: Record<string, string> = {
    not_logged: "bg-muted-foreground/55",
    periods_lost: "bg-muted-foreground/40",
    never_sized: "bg-muted-foreground/25",
    slower: "bg-warning",
  };

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="flex h-2.5 w-full">
        {causes.map((c, i) => c.count > 0 ? (
          <div key={c.key} title={`${c.label}: ${c.count}`}
            className={FILL[c.key]}
            style={{
              width: `${(c.count / total) * 100}%`,
              marginRight: i < causes.length - 1 ? 2 : 0,
            }} />
        ) : null)}
      </div>
      <ul className="divide-y divide-border/60">
        {causes.map((c) => (
          <li key={c.key} className={cn("flex items-start gap-3 px-4 py-2.5",
            c.count === 0 && "opacity-55")}>
            <span className={cn("mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full",
              TONE_DOT[c.count ? tone[c.key] : "neutral"])} />
            <span className="min-w-0 flex-1">
              <span className="block text-[13px] font-medium">{c.label}</span>
              <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                {c.detail}
              </span>
            </span>
            <span className="shrink-0 text-right">
              <span className="block font-mono text-[17px] leading-none tabular-nums">
                {c.count}
              </span>
              {c.behind_topics > 0 ? (
                <span className="mt-1 block font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                  {c.behind_topics} behind
                </span>
              ) : null}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── the scope ledger ─────────────────────────────────────────────────────────

/**
 * The pivot — class, subject or teacher — as ruled rows rather than a table
 * beside a chart of the same thing.
 *
 * The old board drew this data twice: a bar chart of coverage, then a table of
 * the same nodes with a percentage column. One of the two was always redundant,
 * and neither carried the plan. This is both at once: the bar IS the row, and
 * the marker is the thing the chart could never show.
 */
const SCOPE_HEAD: Record<SyllabusScope, string> = {
  school: "Scope", class: "Class", subject: "Subject", teacher: "Teacher",
};

export function ScopeLedger({
  nodes, scope, minCs, minLogged,
}: {
  nodes: SyllabusNode[];
  scope: SyllabusScope;
  minCs: number;
  minLogged: number;
}) {
  if (!nodes.length) {
    return <Empty>Nothing has a syllabus in this scope yet.</Empty>;
  }
  const head = SCOPE_HEAD[scope];

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="hidden grid-cols-[minmax(0,2.2fr)_minmax(0,3fr)_auto_auto] items-center gap-3 border-b border-border bg-muted/25 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground sm:grid">
        <span>{head}</span>
        <span>Against the plan</span>
        <span className="text-right">Of syllabus</span>
        <span className="text-right">Sample</span>
      </div>
      <ul className="divide-y divide-border/60">
        {nodes.map((n) => (
          <li key={n.key}
            className="grid grid-cols-1 items-center gap-x-3 gap-y-2 px-4 py-3 sm:grid-cols-[minmax(0,2.2fr)_minmax(0,3fr)_auto_auto]">
            <span className="min-w-0">
              <span className="block truncate text-[13px] font-medium">{n.label}</span>
              <span className="mt-0.5 block truncate font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                {n.sublabel ?? (scope === "teacher"
                  ? `${n.classes} ${n.classes === 1 ? "class" : "classes"} · ${n.subjects} ${n.subjects === 1 ? "subject" : "subjects"}`
                  : `${n.class_subjects} class-${n.class_subjects === 1 ? "subject" : "subjects"}`)}
              </span>
            </span>

            <span className="min-w-0">
              <span className="flex items-baseline justify-between gap-2">
                <span className={cn("truncate text-[11px] leading-snug",
                  CAPTION_TONE[n.tone])}>
                  {n.pace_caption}
                </span>
                <span className="shrink-0 font-mono text-[12px] tabular-nums">
                  {n.coverage_pct != null ? `${n.coverage_pct}%` : "—"}
                </span>
              </span>
              <span className="mt-1.5 block">
                <PaceBar pct={n.coverage_pct} expectedPct={n.expected_pct}
                  tone={n.tone} height={7} />
              </span>
            </span>

            <span className="text-left font-mono text-[12px] tabular-nums text-muted-foreground sm:text-right">
              <span className="sm:hidden">Of syllabus </span>
              {n.syllabus_pct != null ? `${n.syllabus_pct}%` : "—"}
            </span>

            <span className="text-left sm:text-right">
              {n.rank_eligible ? (
                <span className="font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                  {n.logged_periods} logs
                </span>
              ) : (
                <StateChip>
                  under {minCs} rated{minLogged ? ` / ${minLogged} logs` : ""}
                </StateChip>
              )}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

// ── teacher × class ──────────────────────────────────────────────────────────

const MATRIX_CLASS_CAP = 10;

/**
 * Who teaches what, and how far each of them has got (`D-90`).
 *
 * The scope switcher could already pivot to teacher, and a pivot is a list: it
 * says Ramesh is at 62% and cannot say that his 62% is three classes while a
 * colleague's 71% is one. Load and pace are the same conversation, and this is
 * the only shape that shows them together — the width of a row is the load, the
 * fill of its cells is the pace.
 *
 * Cells are **class-subjects, not an average of them**. Where a teacher takes
 * two subjects in one class the cell stacks both, because averaging a teacher's
 * Maths and Hindi into one number would invent a figure nobody could act on.
 *
 * Nothing is computed here — grouping rows is not arithmetic. Every percentage
 * and every tone is the server's.
 */
export function TeacherMatrix({ rows }: { rows: SyllabusRow[] }) {
  const classLabels = [...new Set(rows.map((r) => r.class_label))].sort();
  const shownClasses = classLabels.slice(0, MATRIX_CLASS_CAP);
  const hiddenClasses = classLabels.length - shownClasses.length;

  const teachers = new Map<string, { name: string; rows: SyllabusRow[] }>();
  for (const r of rows) {
    const key = r.teacher_member_id ?? "unassigned";
    if (!teachers.has(key)) {
      teachers.set(key, { name: r.teacher_name ?? "Unassigned", rows: [] });
    }
    teachers.get(key)!.rows.push(r);
  }
  // Unassigned last: it is a setup gap, not a person, and sorting it into the
  // middle of a list of names invites it to be read as one.
  const ordered = [...teachers.entries()].sort(([ka, a], [kb, b]) =>
    (ka === "unassigned" ? 1 : 0) - (kb === "unassigned" ? 1 : 0)
    || a.name.localeCompare(b.name));

  if (!ordered.length) return <Empty>No class-subject has a teacher yet.</Empty>;

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <div className="overflow-x-auto" style={{ contain: "layout inline-size" }}>
        <table className="w-full border-collapse text-left"
          style={{ minWidth: 220 + shownClasses.length * 116 }}>
          <thead>
            <tr className="border-b border-border bg-muted/25">
              <th className="sticky left-0 z-10 bg-muted/25 px-4 py-2 font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                Teacher
              </th>
              {shownClasses.map((c) => (
                <th key={c}
                  className="px-3 py-2 font-mono text-[10px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ordered.map(([key, t]) => {
              const byClass = new Map<string, SyllabusRow[]>();
              for (const r of t.rows) {
                if (!byClass.has(r.class_label)) byClass.set(r.class_label, []);
                byClass.get(r.class_label)!.push(r);
              }
              return (
                <tr key={key} className="border-t border-border/60 align-top">
                  <th scope="row"
                    className="sticky left-0 z-10 bg-card px-4 py-2.5 text-left align-middle font-normal">
                    <span className="block truncate text-[13px] font-medium">{t.name}</span>
                    <span className="mt-0.5 block font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
                      {byClass.size} {byClass.size === 1 ? "class" : "classes"} ·{" "}
                      {t.rows.length} {t.rows.length === 1 ? "subject" : "subjects"}
                    </span>
                  </th>
                  {shownClasses.map((c) => {
                    const cells = byClass.get(c) ?? [];
                    return (
                      <td key={c} className="px-3 py-2.5">
                        {cells.length ? (
                          <div className="space-y-2">
                            {cells.map((r) => (
                              <div key={r.class_subject_id}>
                                <div className="flex items-baseline justify-between gap-1.5">
                                  <span className="truncate text-[11px] text-muted-foreground"
                                    title={r.subject_name}>
                                    {r.subject_name}
                                  </span>
                                  <span className="shrink-0 font-mono text-[11px] tabular-nums">
                                    {r.status === "unknown" ? "—"
                                      : r.syllabus_pct != null ? `${Math.round(r.syllabus_pct)}%` : "—"}
                                  </span>
                                </div>
                                <div className="mt-1">
                                  <PaceBar
                                    pct={r.status === "unknown" ? null : r.syllabus_pct}
                                    expectedPct={r.expected_syllabus_pct}
                                    tone={toneForStatus(r.status)} height={5} />
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          // Deliberately blank, not a zero: this teacher does
                          // not take this class, which is not 0% coverage.
                          <span className="block text-center font-mono text-[11px] text-muted-foreground/35">
                            ·
                          </span>
                        )}
                      </td>
                    );
                  })}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {hiddenClasses > 0 ? (
        <p className="border-t border-border bg-muted/25 px-4 py-2 text-[11px] text-muted-foreground">
          Showing {shownClasses.length} of {classLabels.length} classes. The full
          set is in the breakdown below — a grid this wide stops being readable
          before it stops fitting.
        </p>
      ) : null}
    </div>
  );
}

// ── will it finish? ──────────────────────────────────────────────────────────

/**
 * The forecast the planner has always computed and no screen has ever drawn.
 *
 * `baseline_finish` and `projected_finish` have ridden on every row since P1
 * and were rendered nowhere, so the board could say a subject was three weeks
 * behind and never the thing an owner actually needs: at this pace it lands
 * after the year ends. That is a decision — drop a chapter, add periods, move
 * an exam — and it has to be visible before the year is too short to take it.
 *
 * Ordered by how far past the year they land, and rows that merely run late
 * against their own baseline are separated from rows that run out of year.
 */
export function FinishForecast({
  rows, limit = 8,
}: {
  rows: SyllabusRow[];
  limit?: number;
}) {
  const at_risk = rows
    .filter((r) => r.overruns_year || (r.overrun_days ?? 0) > 0)
    .sort((a, b) => Number(b.overruns_year) - Number(a.overruns_year)
      || (b.overrun_days ?? 0) - (a.overrun_days ?? 0));
  const shown = at_risk.slice(0, limit);

  if (!shown.length) {
    return (
      <Empty>
        Every planned subject projects to finish inside the year at its current
        pace.
      </Empty>
    );
  }

  const day = (iso: string | null) => iso
    ? new Date(`${iso}T00:00:00`).toLocaleDateString(undefined,
      { day: "numeric", month: "short" })
    : "—";

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <ul className="divide-y divide-border/60">
        {shown.map((r) => (
          <li key={r.class_subject_id}
            className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-2.5">
            <span className={cn("mt-[7px] h-3 w-[2px] shrink-0 self-start rounded-full",
              r.overruns_year ? "bg-danger" : "bg-warning")} />
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium">
                {r.class_label} {r.subject_name}
                {r.teacher_name ? (
                  <span className="font-normal text-muted-foreground"> · {r.teacher_name}</span>
                ) : null}
              </span>
              <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                {r.overruns_year
                  ? "At this pace the portion runs past the end of the year."
                  : `Running ${r.overrun_days} days behind its own plan.`}
              </span>
            </span>
            <span className="shrink-0 text-right font-mono text-[11px] tabular-nums text-muted-foreground">
              <span className="block">plan {day(r.baseline_finish)}</span>
              <span className={cn("block", r.overruns_year ? "text-danger" : "text-warning")}>
                now {day(r.projected_finish)}
              </span>
            </span>
          </li>
        ))}
      </ul>
      {at_risk.length > shown.length ? (
        <p className="border-t border-border bg-muted/25 px-4 py-2 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          +{at_risk.length - shown.length} more running late
        </p>
      ) : null}
    </div>
  );
}
