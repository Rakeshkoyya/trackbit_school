"use client";

import { CalendarCheck, MousePointerClick } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";

const SEEN_KEY = "tb_seen_spotlight";

export function hasSeenSpotlight(): boolean {
  if (typeof window === "undefined") return true;
  return window.localStorage.getItem(SEEN_KEY) === "1";
}

const STEPS = [
  {
    icon: CalendarCheck,
    title: "This is your day",
    body: "Everything assigned to you — or up for grabs — shows up right here. Nothing else to check.",
  },
  {
    icon: MousePointerClick,
    title: "Tap to finish",
    body: "When something's done, tap the circle on its left. That's the whole job.",
  },
];

/**
 * First-run aha (plan §3.5) — a 2-step spotlight, not a tour. Shown once to a
 * fresh member who hasn't finished anything yet. Their first completion then
 * triggers the rich celebration + "See you tomorrow 👋".
 */
export function FirstRunSpotlight({ onDone }: { onDone: () => void }) {
  const [step, setStep] = useState(0);
  const current = STEPS[step];
  const Icon = current.icon;
  const last = step === STEPS.length - 1;

  function finish() {
    if (typeof window !== "undefined") window.localStorage.setItem(SEEN_KEY, "1");
    onDone();
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center bg-background/80 px-5 pb-24 backdrop-blur-sm sm:items-center sm:pb-0">
      <div className="tb-pop-in w-full max-w-sm rounded-2xl border border-border bg-card p-6 shadow-xl">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-accent">
          <Icon className="h-6 w-6 text-accent-foreground" />
        </div>
        <h2 className="mt-4 text-lg font-semibold tracking-tight">{current.title}</h2>
        <p className="mt-1.5 text-sm text-muted-foreground">{current.body}</p>

        <div className="mt-6 flex items-center justify-between">
          <div className="flex gap-1.5">
            {STEPS.map((_, i) => (
              <span
                key={i}
                className={`h-1.5 w-1.5 rounded-full ${i === step ? "bg-primary" : "bg-muted"}`}
              />
            ))}
          </div>
          <div className="flex gap-2">
            {!last ? (
              <Button variant="ghost" size="sm" onClick={finish}>
                Skip
              </Button>
            ) : null}
            <Button size="sm" onClick={() => (last ? finish() : setStep((s) => s + 1))}>
              {last ? "Got it" : "Next"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
