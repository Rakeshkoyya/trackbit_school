"use client";

import { useEffect, useState } from "react";

/** True when the visitor has asked the OS to reduce motion. */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduced(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);
  return reduced;
}

/**
 * Drives a self-looping mockup: cycles 0 → steps-1 → 0 forever, holding longer
 * on the last frame so the finished state can be read before it resets.
 *
 * Reduced-motion callers get the final frame, frozen — the mockups are designed
 * so the last step is the complete, richest state, so a still frame still tells
 * the whole story.
 */
export function useLoopStep(
  steps: number,
  opts: { interval?: number; hold?: number } = {},
): number {
  const { interval = 1400, hold = 2600 } = opts;
  const reduced = useReducedMotion();
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (reduced || steps <= 1) return;
    let timer: ReturnType<typeof setTimeout>;
    const schedule = (current: number) => {
      const delay = current === steps - 1 ? hold : interval;
      timer = setTimeout(() => {
        const next = (current + 1) % steps;
        setStep(next);
        schedule(next);
      }, delay);
    };
    schedule(0);
    return () => clearTimeout(timer);
  }, [steps, interval, hold, reduced]);

  return reduced ? steps - 1 : step;
}
