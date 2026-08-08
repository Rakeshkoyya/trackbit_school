"use client";

import { FeatureGate } from "@/components/plan/upgrade";
import { FEATURES } from "@/lib/features";

/** Lucy is Max (`D-106`). Both roles get the agent when the school has it. */
export default function LucyLayout({ children }: { children: React.ReactNode }) {
  return <FeatureGate feature={FEATURES.agentLucy}>{children}</FeatureGate>;
}
