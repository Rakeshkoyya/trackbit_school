"use client";

/**
 * The band letter, on the ordinal ramp — **one component, because it was
 * written three times before this** (founder review, 2026-08-05).
 *
 * Two rules it exists to keep, both of which a copy would eventually break:
 *
 * · **The ink is a token, never a fixed white.** The A/B/C ramp is ordinal and
 *   INVERTS between themes — light mode runs A pale → C dark, dark mode the
 *   other way, because on a dark surface "more" has to read brighter. So one
 *   fixed foreground fails at whichever end is currently pale: white on
 *   light-mode A is 2.28:1, and on dark-mode C it is 1.55:1, which is a letter
 *   nobody can read. `--band-ink-*` is chosen per tier per theme, all ≥ 4.5:1.
 *
 * · **Not assessed is a WORD, never a fourth tier** (ux §5). It wears the
 *   dashed no-record texture the register (V1-14), the day-book (V1-16) and the
 *   homework funnel (V1-17) already use, so a gap in the record can never be
 *   mistaken for a measured result.
 *
 * `S-166` — the letter never travels without its sentence. On a dense row the
 * descriptor is the title; the full text belongs on the child's own page.
 *
 * Deliberately NOT the status palette: painting C red turns a teaching group
 * into a verdict on a child (P4's whole point).
 */

import type { BandTier } from "@/lib/school-types";
import { cn } from "@/lib/utils";

export function BandChip({
  tier,
  descriptor,
  className,
}: {
  tier: BandTier | null;
  descriptor?: string | null;
  className?: string;
}) {
  if (!tier) {
    return (
      <span
        className={cn(
          "rounded-md border border-dashed border-border px-1.5 py-0.5 text-[11px] text-muted-foreground",
          className,
        )}
      >
        not assessed
      </span>
    );
  }
  const t = tier.toLowerCase();
  return (
    <span
      title={descriptor ?? undefined}
      className={cn(
        "rounded-md px-1.5 py-0.5 font-mono text-[11px] font-semibold",
        className,
      )}
      style={{ background: `var(--band-${t})`, color: `var(--band-ink-${t})` }}
    >
      {tier}
    </span>
  );
}
