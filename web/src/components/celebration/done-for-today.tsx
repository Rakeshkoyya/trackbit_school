"use client";

import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";

export interface RitualPayload {
  doneCount: number;
  line: string; // one contextual line of meaning
}

/**
 * The "done for today" ritual (plan §3.2) — the permission-to-stop moment.
 * No upsell, no "do more". Just acknowledgement.
 */
export function DoneForToday({ payload, onDismiss }: { payload: RitualPayload; onDismiss: () => void }) {
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-background/95 px-6 backdrop-blur-sm">
      <div className="tb-ritual-in flex max-w-sm flex-col items-center text-center">
        <div className="tb-pop-in flex h-20 w-20 items-center justify-center rounded-full bg-[#e7efe9]">
          <Check className="h-10 w-10 text-success" strokeWidth={2.5} />
        </div>
        <h2 className="mt-6 text-2xl font-semibold tracking-tight">You&apos;re done for today</h2>
        <p className="mt-2 text-muted-foreground">
          {payload.doneCount} {payload.doneCount === 1 ? "thing" : "things"} finished.
        </p>
        <p className="mt-4 text-sm text-accent-foreground">{payload.line}</p>
        <Button variant="ghost" className="mt-8" onClick={onDismiss}>
          Done
        </Button>
      </div>
    </div>
  );
}
