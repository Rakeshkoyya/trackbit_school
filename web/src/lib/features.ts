/**
 * Package tiers, client side — the pure half (`D-106`).
 *
 * The browser holds **no copy of the tier map**. The server computes
 * `me.org.features` from `api/app/core/features.py`; this file only supplies
 * the lookup keys and the wall's copy. That is deliberate: the most-repeated
 * defect in this codebase is the same fact computed two ways, and a tier is
 * exactly that kind of fact — a second copy here would drift the day a feature
 * moves between tiers, and nobody would notice until a school saw the wrong
 * lock.
 *
 * **Components ask for a FEATURE, never for a plan.** There is no
 * `plan === "max"` anywhere in `web/`, and there should never be one.
 *
 * Kept free of React and of `auth-context` on purpose: `nav-items.ts` imports
 * these constants, and `auth-context` imports `nav-items`, so anything
 * hook-shaped here would close an import cycle. The hooks live in
 * `lib/use-feature.ts`.
 */

export type PlanLabel = "Free" | "Pro" | "Max" | "Ultra";

/** The feature ids the UI references. Mirrors `core/features.Feature`, but as
 *  plain strings — a lookup key, not a second source of truth. */
export const FEATURES = {
  studentsAcademics: "students.academics",
  homeworkDesk: "homework.desk",
  examsBoard: "exams.board",
  feesCollection: "fees.collection",
  staffRoster: "staff.roster",
  tasksBoards: "tasks.boards",
  insightsActions: "insights.actions",
  sessionsHostel: "sessions.hostel",
  parentPortal: "parent.portal",
  commsGuardian: "comms.guardian",
  agentLucy: "agent.lucy",
  agentMcp: "agent.mcp",
} as const;

export type FeatureId = (typeof FEATURES)[keyof typeof FEATURES];

/** Cheapest tier that unlocks each gated feature — for wall COPY only.
 *  The server decides what is actually allowed; this only names the tier so the
 *  wall can say "Pro unlocks…" without a round-trip. */
const UNLOCKED_BY: Record<string, PlanLabel> = {
  "students.academics": "Pro",
  "homework.desk": "Pro",
  "exams.board": "Pro",
  "fees.collection": "Pro",
  "staff.roster": "Max",
  "tasks.boards": "Max",
  "insights.actions": "Max",
  "sessions.hostel": "Max",
  "parent.portal": "Max",
  "comms.guardian": "Max",
  "agent.lucy": "Max",
  "exams.capture_advanced": "Max",
  "agent.mcp": "Ultra",
};

export function tierLabelFor(feature: string): PlanLabel {
  return UNLOCKED_BY[feature] ?? "Pro";
}

/** Paise → "₹1,234". Money crosses the wire as integer paise and is formatted
 *  once, here, so the wall, the plan screen and the operator list agree. */
export function formatPaise(paise: number): string {
  return `₹${Math.round(paise / 100).toLocaleString("en-IN")}`;
}
