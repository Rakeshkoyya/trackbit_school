"use client";

import { FeatureGate } from "@/components/plan/upgrade";
import { FEATURES } from "@/lib/features";

/** Boards are the Tasks module under another door (`D-109` — Max, whole).
 *
 *  `/tasks` was gated but `/boards/[id]` was not, so a locked school could
 *  still reach a board by URL and meet a half-working screen. A screen
 *  reachable by URL is a screen that has to be gated. */
export default function BoardsLayout({ children }: { children: React.ReactNode }) {
  return <FeatureGate feature={FEATURES.tasksBoards}>{children}</FeatureGate>;
}
