"use client";

/**
 * The wizard frame (V2-P7): a full-page, two-column stage.
 *
 * Left  — one question at a time, with its controls.
 * Right — the live artifact that question is shaping (the year, the roster, the grid).
 *
 * Every step writes through to the real tables the moment it is confirmed, so
 * `progress` on the server is always the truth and the rail below is never a lie.
 * Nothing here is modal, and nothing blocks: a step can be skipped and returned to.
 */

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { Check } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import type { WizardStep } from "@/lib/school-types";

export function StepRail({
  steps,
  current,
  onJump,
}: {
  steps: WizardStep[];
  current: number;
  onJump: (index: number) => void;
}) {
  return (
    <nav aria-label="Setup steps" className="flex flex-wrap gap-1.5">
      {steps.map((s) => {
        const active = s.index === current;
        return (
          <button
            key={s.key}
            type="button"
            onClick={() => onJump(s.index)}
            aria-current={active ? "step" : undefined}
            className={cn(
              "group inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors",
              active
                ? "border-primary bg-primary text-primary-foreground"
                : s.complete
                  ? "border-border bg-card text-foreground hover:bg-muted"
                  : "border-dashed border-border text-muted-foreground hover:bg-muted",
            )}
          >
            <span
              className={cn(
                "flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-semibold",
                active
                  ? "bg-primary-foreground/20"
                  : s.complete
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground",
              )}
            >
              {s.complete && !active ? <Check className="h-2.5 w-2.5" /> : s.index}
            </span>
            {s.title}
          </button>
        );
      })}
    </nav>
  );
}

export function StepFrame({
  stepKey,
  title,
  blurb,
  children,
  aside,
  footer,
}: {
  stepKey: string;
  title: string;
  blurb?: ReactNode;
  children: ReactNode;
  aside?: ReactNode;
  footer?: ReactNode;
}) {
  const reduce = useReducedMotion();
  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={stepKey}
        initial={reduce ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        exit={reduce ? undefined : { opacity: 0, y: -8 }}
        transition={reduce ? { duration: 0 } : { duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
        className="grid flex-1 grid-cols-1 gap-8 lg:grid-cols-[minmax(0,420px)_minmax(0,1fr)]"
      >
        <div className="flex min-w-0 flex-col">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {blurb ? <p className="mt-1.5 text-sm text-muted-foreground">{blurb}</p> : null}
          <div className="mt-6 min-h-0 flex-1 space-y-4">{children}</div>
          {footer ? <div className="mt-6">{footer}</div> : null}
        </div>
        <div className="min-w-0">{aside}</div>
      </motion.div>
    </AnimatePresence>
  );
}

/** A right-hand artifact panel. Sticky so it stays put while the left column scrolls. */
export function Aside({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <div className="lg:sticky lg:top-6">
      {title ? (
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {title}
        </h2>
      ) : null}
      {children}
    </div>
  );
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-card px-3 py-2">
      <div className="text-lg font-semibold tabular-nums">{value}</div>
      <div className="text-[11px] text-muted-foreground">{label}</div>
    </div>
  );
}
