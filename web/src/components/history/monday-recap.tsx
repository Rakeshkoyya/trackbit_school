"use client";

import { Sparkles, X } from "lucide-react";
import { useState } from "react";

import type { History } from "@/lib/types";

/**
 * Monday recap card (plan §3.4) — one positive stat + a gentle forward look,
 * dismissible, shown only on Monday. Mirrors the weekly digest's tone.
 */
export function MondayRecap({ hist }: { hist: History | undefined }) {
  const isMonday = new Date().getDay() === 1;
  const lastWeek = hist && hist.weekly.length >= 2 ? hist.weekly[hist.weekly.length - 2] : undefined;
  const storageKey = lastWeek ? `tb_recap_${lastWeek.week_start}` : "";
  const [dismissed, setDismissed] = useState(() => {
    if (typeof window === "undefined" || !storageKey) return false;
    return window.localStorage.getItem(storageKey) === "1";
  });

  if (!isMonday || !hist || !lastWeek || lastWeek.count === 0 || dismissed) return null;

  // Busiest day of last week, from the dot calendar.
  const start = lastWeek.week_start;
  const end = new Date(new Date(start + "T00:00:00").getTime() + 6 * 86_400_000)
    .toISOString()
    .slice(0, 10);
  const weekDots = hist.dots.filter((d) => d.date >= start && d.date <= end && d.done > 0);
  const busiest = weekDots.reduce<(typeof weekDots)[number] | null>(
    (best, d) => (best === null || d.done > best.done ? d : best),
    null,
  );
  const busiestLabel = busiest
    ? new Date(busiest.date + "T00:00:00").toLocaleDateString(undefined, { weekday: "long" })
    : null;

  function dismiss() {
    if (storageKey) window.localStorage.setItem(storageKey, "1");
    setDismissed(true);
  }

  return (
    <div className="mb-5 flex items-start gap-3 rounded-xl border border-border bg-accent/40 p-4">
      <Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-success" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">Last week: {lastWeek.count} done</p>
        <p className="mt-0.5 text-sm text-muted-foreground">
          {busiestLabel ? `Busiest day was ${busiestLabel}. ` : ""}Fresh week ahead — one thing at a
          time.
        </p>
      </div>
      <button onClick={dismiss} aria-label="Dismiss" className="shrink-0 text-muted-foreground hover:text-foreground">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}
