"use client";

import { createContext, useCallback, useContext, useState } from "react";

import { DoneForToday, type RitualPayload } from "./done-for-today";
import { SparkleBurst } from "./sparkle-burst";

interface CelebrationApi {
  // Call on every completion; ~1 in 7 fires the richer sparkle (variable reward).
  onCompletion: (opts?: { force?: boolean }) => void;
  showRitual: (payload: RitualPayload) => void;
}

const Ctx = createContext<CelebrationApi | null>(null);

export function CelebrationProvider({ children }: { children: React.ReactNode }) {
  const [sparkleKey, setSparkleKey] = useState<number | null>(null);
  const [ritual, setRitual] = useState<RitualPayload | null>(null);

  const onCompletion = useCallback((opts?: { force?: boolean }) => {
    const lucky = opts?.force || Math.random() < 1 / 7;
    if (lucky) {
      const k = Date.now();
      setSparkleKey(k);
      window.setTimeout(() => setSparkleKey((cur) => (cur === k ? null : cur)), 700);
    }
  }, []);

  const showRitual = useCallback((payload: RitualPayload) => setRitual(payload), []);

  return (
    <Ctx.Provider value={{ onCompletion, showRitual }}>
      {children}
      {sparkleKey !== null ? <SparkleBurst key={sparkleKey} /> : null}
      {ritual ? <DoneForToday payload={ritual} onDismiss={() => setRitual(null)} /> : null}
    </Ctx.Provider>
  );
}

export function useCelebration() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useCelebration must be used within <CelebrationProvider>");
  return ctx;
}
