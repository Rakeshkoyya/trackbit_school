/**
 * What a period *is*, and what it asks the teacher for (TT-2).
 *
 * Mirrors `api/app/core/day_shape.py`. Changing one means changing both — the
 * server validates writes against its copy, so a screen that offers a tab this
 * table does not allow is a screen that collects a tap and then 422s.
 *
 * The capture flags also arrive on the wire (`MeetingOut.capture`), and the
 * runtime should prefer those: the server knows the block's real kind. This
 * table is for the surfaces that only have a kind string — a My Day row, a grid
 * cell — and for labels.
 */

export type SlotType = "subject" | "block";

export type BlockKind =
  | "homework"
  | "study"
  | "sports"
  | "activity"
  | "course"
  | "assembly";

export interface BlockCapture {
  label: string;
  /** One line under the name on My Day, before anything has been captured. */
  hint: string;
  /** Its own roll, against its own roster — never the school-day register. */
  roll: boolean;
  /** One note for the whole block: "what we covered today". */
  classLog: boolean;
  /** Per-student sections, like the class deep log. */
  studentLogs: boolean;
  /** Photos and videos on the meeting, and where allowed on a student. */
  memories: boolean;
  /** The class → subject → check-the-books flow. */
  homeworkCheck: boolean;
}

export const BLOCK_CAPTURE: Record<BlockKind, BlockCapture> = {
  homework: {
    label: "Homework class",
    hint: "Check tonight's homework",
    roll: true, classLog: false, studentLogs: true, memories: true,
    homeworkCheck: true,
  },
  study: {
    label: "Study / prep",
    hint: "Evening prep",
    roll: true, classLog: false, studentLogs: true, memories: true,
    homeworkCheck: false,
  },
  sports: {
    label: "Sports",
    hint: "Games and practice",
    roll: true, classLog: false, studentLogs: false, memories: true,
    homeworkCheck: false,
  },
  activity: {
    label: "Activity",
    hint: "Club or activity",
    roll: true, classLog: true, studentLogs: false, memories: true,
    homeworkCheck: false,
  },
  course: {
    label: "Extra course",
    hint: "Extra course",
    roll: true, classLog: true, studentLogs: true, memories: true,
    homeworkCheck: false,
  },
  assembly: {
    label: "Assembly / yoga",
    // Whole-school time. Nobody takes a roll at assembly, and asking for one
    // would be exactly the mandatory per-student capture P1v2 forbids.
    hint: "Whole-school time",
    roll: false, classLog: false, studentLogs: false, memories: true,
    homeworkCheck: false,
  },
};

/** Ordered for the admin's picker — deterministic, never reshuffled. */
export const BLOCK_KINDS: BlockKind[] = [
  "homework", "study", "sports", "activity", "course", "assembly",
];

export const DEFAULT_BLOCK_KIND: BlockKind = "study";

/**
 * What this kind captures. An unknown kind degrades to `study` rather than
 * throwing: a block written by a newer server must still render here.
 */
export function captureFor(kind: string | null | undefined): BlockCapture {
  return BLOCK_CAPTURE[(kind ?? "") as BlockKind] ?? BLOCK_CAPTURE[DEFAULT_BLOCK_KIND];
}

export function blockLabel(kind: string | null | undefined): string {
  return captureFor(kind).label;
}

/** "08:00–08:40", or "" when the school never set its timings. */
export function timeRange(start?: string | null, end?: string | null): string {
  if (!start) return "";
  return end ? `${start}–${end}` : start;
}
