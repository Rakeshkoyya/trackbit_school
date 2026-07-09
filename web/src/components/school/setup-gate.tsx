"use client";

/**
 * The nudge into setup (SPRD2 §5.1).
 *
 * A banner, not a forced redirect. A director who has deliberately skipped a step
 * — or who is mid-year and only wants the dashboard — must never be trapped in the
 * wizard. It disappears on its own once `status` is "done", because that flag is
 * server state derived from the real tables.
 */

import { useQuery } from "@tanstack/react-query";
import { motion, useReducedMotion } from "framer-motion";
import { ArrowRight, Sparkles } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { schoolApi } from "@/lib/school-api";

export function SetupGate() {
  const reduce = useReducedMotion();
  const { data } = useQuery({ queryKey: ["wizard"], queryFn: schoolApi.wizardState });
  if (!data || data.status === "done") return null;

  const done = data.steps.filter((s) => s.complete).length;
  const total = data.steps.length;
  const started = done > 0;

  return (
    <motion.div
      initial={reduce ? false : { opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="mb-6 overflow-hidden rounded-2xl border border-border bg-card"
    >
      <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <h2 className="text-sm font-semibold">
              {started ? "Finish setting up your year" : "Set up your academic year"}
            </h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {started
              ? `${done} of ${total} steps done. Pick up where you left off.`
              : "Ten steps: your calendar, staff, syllabus and timetable become a day-by-day plan."}
          </p>
          {started ? (
            <div
              className="mt-3 h-1.5 w-full max-w-sm overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-valuenow={done}
              aria-valuemin={0}
              aria-valuemax={total}
            >
              <motion.div
                className="h-full rounded-full bg-primary"
                initial={{ width: 0 }}
                animate={{ width: `${(done / total) * 100}%` }}
                transition={reduce ? { duration: 0 } : { duration: 0.5, ease: "easeOut" }}
              />
            </div>
          ) : null}
        </div>
        <Link href="/setup/wizard" className="shrink-0">
          <Button>
            {started ? "Continue setup" : "Start setup"} <ArrowRight className="h-4 w-4" />
          </Button>
        </Link>
      </div>
    </motion.div>
  );
}
