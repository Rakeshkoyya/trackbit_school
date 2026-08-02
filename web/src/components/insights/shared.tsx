"use client";

// The pieces every dashboard tab is made of (DASH3 §7).
//
// Deliberately small and shared, because the six modules must read as one board
// rather than six screens: the same section heading, the same empty state, the
// same red-row shape, the same "already done today" affordance. Charts come from
// `components/charts` — this file adds only the non-chart furniture.

import Link from "next/link";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type Tone = "neutral" | "green" | "amber" | "red";

export const TONE_TEXT: Record<Tone, string> = {
  neutral: "text-muted-foreground",
  green: "text-success",
  amber: "text-warning",
  red: "text-danger",
};

export const TONE_BADGE: Record<Tone, "neutral" | "success" | "warning" | "danger"> = {
  neutral: "neutral",
  green: "success",
  amber: "warning",
  red: "danger",
};

export function toneFor(pct: number | null | undefined, good = 75, fair = 60): Tone {
  if (pct == null) return "neutral";
  return pct >= good ? "green" : pct >= fair ? "amber" : "red";
}

export const pct = (v: number | null | undefined, digits = 0) =>
  v == null ? "—" : `${(v * 100).toFixed(digits)}%`;

export const dayLabel = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/** A titled block. One heading style across all seven tabs. */
export function Section({
  title, hint, action, children, className = "",
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("mb-6", className)}>
      <div className="mb-2 flex flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold">{title}</h2>
          {hint ? <p className="mt-0.5 text-xs text-muted-foreground">{hint}</p> : null}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/** The one empty state. Says what would fill it, never just "no data". */
export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
      {children}
    </p>
  );
}

/** Skeleton for a whole tab, so a slow board doesn't flash an empty page. */
export function BoardSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 animate-pulse rounded-xl border border-border bg-card" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-48 animate-pulse rounded-xl border border-border bg-card" />
      ))}
    </div>
  );
}

/**
 * A red row: what is wrong, who it is about, and the buttons that fix it.
 *
 * `done` is not an error state — it is the rail refusing to fire twice in one
 * day, which is the whole reason `followup_actions` exists. It reads as a quiet
 * confirmation, never as a failure.
 */
export function RedRow({
  title, subtitle, meta, tone = "red", actions, href,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  meta?: ReactNode;
  tone?: Tone;
  actions?: ReactNode;
  href?: string;
}) {
  const dot = { neutral: "bg-muted-foreground", green: "bg-success", amber: "bg-warning", red: "bg-danger" }[tone];
  const body = (
    <>
      <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", dot)} />
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-medium">{title}</span>
        {subtitle ? <span className="mt-0.5 block text-xs text-muted-foreground">{subtitle}</span> : null}
      </span>
    </>
  );
  // `meta` is a SIBLING of the link, never inside it (V1-13). The reach board
  // puts a `tel:` link in meta, and an <a> inside an <a> is invalid HTML that
  // React reports as a hydration error — and the phone number, which is the
  // whole point of that row, stops being separately tappable.
  return (
    <div className="flex flex-wrap items-start gap-3 rounded-lg border border-border bg-card px-4 py-3">
      {href ? (
        <Link href={href} className="flex min-w-0 flex-1 items-start gap-3 hover:underline">{body}</Link>
      ) : (
        <div className="flex min-w-0 flex-1 items-start gap-3">{body}</div>
      )}
      {/* No `shrink-0` on either: at 360px a long meta ("Over the monthly limit
          — 3 days in August…") or a wordy action ("Ask for a catch-up plan")
          pushed the whole page into horizontal scroll. */}
      {meta ? <span className="min-w-0 text-right text-xs text-muted-foreground">{meta}</span> : null}
      {actions ? <div className="flex min-w-0 flex-wrap items-center gap-1.5">{actions}</div> : null}
    </div>
  );
}

/** A rail button that knows it has already fired today. */
export function RailButton({
  label, doneLabel, done, pending, onClick, icon,
}: {
  label: string;
  doneLabel: string;
  done: boolean;
  pending?: boolean;
  onClick: () => void;
  icon?: ReactNode;
}) {
  if (done) {
    return <Badge tone="success" className="px-2 py-1">{icon}{doneLabel}</Badge>;
  }
  return (
    <Button size="sm" variant="outline" onClick={onClick} disabled={pending}>
      {icon}{label}
    </Button>
  );
}

/**
 * A state that is NOT a rating — `unplanned`, `unallocated`, `not enough data`.
 * Rendered as words in a neutral chip so it can never be mistaken for a colour
 * on the RAG scale (V2-P11; DASH3 §4.2).
 */
export function StateChip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-md border border-dashed border-border px-1.5 py-0.5 text-[11px] text-muted-foreground">
      {children}
    </span>
  );
}

/** Horizontal scroll container for wide tables — the page body never scrolls. */
export function ScrollX({ children }: { children: ReactNode }) {
  return <div className="-mx-1 overflow-x-auto px-1">{children}</div>;
}
