"use client";

/**
 * The lock on Plan → Exams.
 *
 * `/main-exams` has been gated behind `Feature.EXAMS_BOARD` (a PRO feature)
 * since tiers shipped — `api/app/api/v1/router.py` mounts it with
 * `_gate(Feature.EXAMS_BOARD)`. Every other paid area wraps its layout in
 * `FeatureGate` so a Free school meets the upgrade wall; this one never did.
 *
 * The result was the worst possible rendering of a lock: the board's query got
 * a **402**, `MainExamBoardView` fell through its `if (!data) return null`, and
 * an admin on Free saw the page header, the year switcher, and then nothing at
 * all — no exams, no "Add exam", no explanation. The school's five exams were
 * sitting in `calendar_events` the whole time.
 *
 * `D-111`'s rule is that nothing disappears: she still sees the tab, still
 * lands on the page, and is told what unlocks it and what it costs.
 */

import { FeatureGate } from "@/components/plan/upgrade";
import { FEATURES } from "@/lib/features";

export default function PlanExamsLayout({ children }: { children: React.ReactNode }) {
  return <FeatureGate feature={FEATURES.examsBoard}>{children}</FeatureGate>;
}
