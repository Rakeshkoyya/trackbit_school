"use client";

// The overview's furniture: the action rail and the module blocks.
//
// The overview used to be six one-number tiles. A tile could say "78%" in a
// second, but not what was 78% or who — so the admin opened a tab to find out,
// every morning, for every module. A block instead carries the sentence, the
// two or three figures that mean something together, and the NAMED specifics
// underneath. The tab is still where the work happens; this only makes opening
// one a decision rather than a search.
//
// Nothing here computes anything. Every figure, every phrase and every tone
// arrives from `services/insights/overview.py`, so the summary can never drift
// from the tab it links to.

import {
  ArrowRight, BookOpen, ChevronRight, ClipboardList, GraduationCap,
  NotebookPen, UserCheck, Users, Wallet,
} from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

import { Sparkline, STATUS_COLOR } from "@/components/charts";
import type { OverviewMetric, OverviewNote, OverviewSection, QuickAction } from "@/lib/insights-types";
import { cn } from "@/lib/utils";

import type { Tone } from "./shared";

/** Values carry tone only when the tone MEANS something — neutral inherits the
 *  body colour rather than greying out a perfectly fine number. */
const VALUE_TONE: Record<Tone, string> = {
  neutral: "", green: "text-success", amber: "text-warning", red: "text-danger",
};

const DOT: Record<Tone, string> = {
  neutral: "bg-muted-foreground/40", green: "bg-success",
  amber: "bg-warning", red: "bg-danger",
};

const ACCENT: Record<Tone, string> = {
  neutral: "border-border bg-card hover:border-primary/40",
  green: "border-border bg-card hover:border-primary/40",
  amber: "border-warning/35 bg-warning/6 hover:border-warning/60",
  red: "border-danger/35 bg-danger/6 hover:border-danger/60",
};

const ICON: Record<string, ReactNode> = {
  attendance: <UserCheck className="h-4 w-4" />,
  staff: <Users className="h-4 w-4" />,
  syllabus: <BookOpen className="h-4 w-4" />,
  homework: <NotebookPen className="h-4 w-4" />,
  tasks: <ClipboardList className="h-4 w-4" />,
  exams: <GraduationCap className="h-4 w-4" />,
  fees: <Wallet className="h-4 w-4" />,
};

// ── the rail ─────────────────────────────────────────────────────────────────

/**
 * What is waiting on this person right now, each with the screen that clears it.
 *
 * Deliberately separate from the alert feed below: an alert describes the
 * school and gets filed as a task, an action is a thing to go and do. The rail
 * is derived server-side, so it empties itself as the day is dealt with — an
 * empty rail is a real all-clear, not a feature nobody wired up.
 */
export function ActionRail({ actions }: { actions: QuickAction[] }) {
  if (!actions.length) {
    return (
      <p className="rounded-xl border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
        Nothing is waiting on you — attendance, cover and approvals are all clear.
      </p>
    );
  }
  return (
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
      {actions.map((a) => (
        <Link key={a.key} href={a.href}
          className={cn("group flex items-center gap-3 rounded-xl border px-3.5 py-3 transition-colors",
            ACCENT[a.tone])}>
          {a.count > 0 ? (
            <span className={cn(
              "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-sm font-semibold tabular-nums",
              a.tone === "red" ? "bg-danger/12 text-danger"
                : a.tone === "amber" ? "bg-warning/12 text-warning"
                  : "bg-muted text-muted-foreground")}>
              {a.count}
            </span>
          ) : (
            <span className={cn("h-8 w-1 shrink-0 rounded-full", DOT[a.tone])} />
          )}
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-medium">{a.label}</span>
            {/* Two lines: the detail is the whole reason the item is actionable,
                and "15 periods today have no teacher …" is not. */}
            <span className="line-clamp-2 text-xs leading-snug text-muted-foreground">{a.detail}</span>
          </span>
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
        </Link>
      ))}
    </div>
  );
}

// ── a module block ───────────────────────────────────────────────────────────

function Metric({ metric }: { metric: OverviewMetric }) {
  const spark = metric.spark.filter((v) => v != null);
  const body = (
    <>
      {/* Two lines reserved, wrapping rather than truncating: at three columns a
          truncated label reads "UNCHECKED PAST …", and the fixed height keeps
          every value on the same baseline whether its label wraps or not. */}
      <p className="min-h-[26px] text-[11px] font-medium uppercase leading-[13px] tracking-wide text-muted-foreground">
        {metric.label}
      </p>
      {/* Three money values in three columns overflow a phone, so the figure
          steps down a size below `sm` rather than truncating a rupee amount. */}
      <p className={cn("mt-1 truncate text-lg font-semibold leading-none tabular-nums sm:text-[22px]",
        VALUE_TONE[metric.tone])}>
        {metric.value}
      </p>
      {metric.sub ? (
        <p className="mt-1.5 text-[11px] leading-snug text-muted-foreground">{metric.sub}</p>
      ) : null}
      {spark.length > 1 ? (
        <div className="-mx-1 mt-1.5">
          <Sparkline values={metric.spark} height={24} color={STATUS_COLOR[metric.tone]} />
        </div>
      ) : null}
    </>
  );
  const cls = "min-w-0 flex-1 px-3 py-3 sm:px-4";
  return metric.href
    ? <Link href={metric.href} className={cn(cls, "transition-colors hover:bg-muted/40")}>{body}</Link>
    : <div className={cls}>{body}</div>;
}

function Note({ note }: { note: OverviewNote }) {
  const body = (
    <>
      <span className={cn("mt-[7px] h-1.5 w-1.5 shrink-0 rounded-full", DOT[note.tone])} />
      <span className="min-w-0 flex-1 truncate">{note.text}</span>
    </>
  );
  return (
    <li className="text-xs">
      {note.href ? (
        <Link href={note.href} className="flex items-start gap-2 hover:underline">{body}</Link>
      ) : (
        <span className="flex items-start gap-2">{body}</span>
      )}
    </li>
  );
}

/**
 * One module, summarised. The header says which it is and links to its tab; the
 * sentence says how it is going; the metrics give the figures that sentence
 * rests on; the notes name the rows behind them.
 */
export function SectionCard({
  section,
}: {
  section: OverviewSection;
}) {
  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-border bg-card">
      <header className="flex items-center gap-2 border-b border-border px-4 py-2.5">
        <span className="text-muted-foreground">{ICON[section.key]}</span>
        <h3 className="text-sm font-semibold">{section.label}</h3>
        {section.tone !== "neutral" && section.tone !== "green" ? (
          <span className={cn("h-1.5 w-1.5 rounded-full", DOT[section.tone])} />
        ) : null}
        <Link href={section.href}
          className="ml-auto inline-flex shrink-0 items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground">
          Open <ArrowRight className="h-3 w-3" />
        </Link>
      </header>

      <p className="px-4 pt-3 text-sm leading-relaxed">{section.headline}</p>

      <div className="flex divide-x divide-border">
        {section.metrics.map((m) => <Metric key={m.key} metric={m} />)}
      </div>

      {section.notes.length ? (
        <ul className="mt-auto space-y-1.5 border-t border-border bg-muted/25 px-4 py-2.5">
          {section.notes.map((n, i) => <Note key={i} note={n} />)}
        </ul>
      ) : null}
    </section>
  );
}

/**
 * The same block for something the insights board does not own — fees, which
 * live on their own screen and stay admin-only by dint of the payload they come
 * from (teachers never receive a fee figure at all, §2 hard rule).
 */
export function CustomSection({
  sectionKey, label, href, headline, children, notes,
}: {
  sectionKey: string;
  label: string;
  href: string;
  headline: string;
  children: ReactNode;
  notes?: ReactNode;
}) {
  return (
    <section className="flex flex-col overflow-hidden rounded-xl border border-border bg-card">
      <header className="flex items-center gap-2 border-b border-border px-4 py-2.5">
        <span className="text-muted-foreground">{ICON[sectionKey]}</span>
        <h3 className="text-sm font-semibold">{label}</h3>
        <Link href={href}
          className="ml-auto inline-flex shrink-0 items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground">
          Open <ArrowRight className="h-3 w-3" />
        </Link>
      </header>
      <p className="px-4 pt-3 text-sm leading-relaxed">{headline}</p>
      <div className="flex divide-x divide-border">{children}</div>
      {notes ? (
        <div className="mt-auto border-t border-border bg-muted/25 px-4 py-2.5 text-xs">{notes}</div>
      ) : null}
    </section>
  );
}

/** A metric cell for `CustomSection`, so a hand-built block matches the rest. */
export function MetricCell({
  label, value, sub, tone = "neutral", href,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: Tone;
  href?: string;
}) {
  return <Metric metric={{ key: label, label, value, sub: sub ?? null, tone, href: href ?? null, spark: [] }} />;
}
