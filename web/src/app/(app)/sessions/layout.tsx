"use client";

import { FeatureGate } from "@/components/plan/upgrade";
import { FEATURES } from "@/lib/features";

/** Hostel and activity sessions are Max (`D-106`). */
export default function SessionsLayout({ children }: { children: React.ReactNode }) {
  return <FeatureGate feature={FEATURES.sessionsHostel}>{children}</FeatureGate>;
}
