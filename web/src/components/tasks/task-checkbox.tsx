"use client";

import { Check } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * The completion checkbox — spring pop + haptic, then fires onComplete.
 * Optimistic UI lives in the parent; this owns only the micro-interaction.
 */
export function TaskCheckbox({
  checked,
  onComplete,
  disabled,
}: {
  checked: boolean;
  onComplete: () => void;
  disabled?: boolean;
}) {
  const [popping, setPopping] = useState(false);

  function handle(e: React.MouseEvent) {
    e.stopPropagation();
    e.preventDefault();
    if (disabled || checked) return;
    setPopping(true);
    if (typeof navigator !== "undefined" && "vibrate" in navigator) {
      navigator.vibrate?.(12);
    }
    window.setTimeout(() => setPopping(false), 240);
    onComplete();
  }

  return (
    <button
      type="button"
      aria-label={checked ? "Completed" : "Mark done"}
      onClick={handle}
      disabled={disabled}
      className={cn(
        "flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
        checked
          ? "border-success bg-success text-success-foreground"
          : "border-muted-foreground/40 text-transparent hover:border-success",
        popping && "tb-check-pop",
      )}
    >
      <Check className="h-3.5 w-3.5" strokeWidth={3} />
    </button>
  );
}
